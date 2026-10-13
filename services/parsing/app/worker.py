"""Worker: resume.uploaded -> extract -> split -> resume-service PATCH -> resume.parsed."""

import json
import logging
import os
import threading

import boto3
import httpx

log = logging.getLogger("parsing-worker")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC_IN = os.getenv("KAFKA_TOPIC_IN", "resume.uploaded")
TOPIC_OUT = os.getenv("KAFKA_TOPIC_OUT", "resume.parsed")
RESUME_API = os.getenv("RESUME_API", "http://resume-service:8002")
S3_BUCKET = os.getenv("S3_BUCKET", "resumes")

_producer = None
_thread: threading.Thread | None = None


def s3_get(key: str) -> bytes:
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://s3:4566"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return obj["Body"].read()


def producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode(),
            request_timeout_ms=3000,
        )
    except Exception as e:
        log.warning("kafka producer unavailable: %s", e)
        _producer = None
    return _producer


def handle_event(event: dict) -> dict:
    """Pure-ish pipeline step, unit-tested without kafka/s3."""
    from .extract import extract_pdf
    from .sections import split_sections

    resume_id = event["resume_id"]
    data = s3_get(event["s3_key"])
    extracted = extract_pdf(data)
    if extracted["needs_ocr"]:
        # OCR (TrOCR) lands in a later cycle; mark so the UI can show it.
        parsed = {"_needs_ocr": True, "pages": extracted["pages"]}
        status = "needs_ocr"
    else:
        parsed = split_sections(extracted["text"])
        parsed["_pages"] = extracted["pages"]
        status = "parsed"
    with httpx.Client(timeout=10.0) as client:
        client.patch(f"{RESUME_API}/internal/resumes/{resume_id}/parsed", json={"status": status, "parsed": parsed})
    p = producer()
    if p is not None:
        try:
            p.send(TOPIC_OUT, {"resume_id": resume_id, "status": status}).get(timeout=5)
        except Exception as e:
            log.warning("publish failed: %s", e)
    else:
        log.info("event %s %s", TOPIC_OUT, {"resume_id": resume_id, "status": status})
    return {"resume_id": resume_id, "status": status}


def _loop() -> None:
    import time

    while True:
        try:
            from kafka import KafkaConsumer
            consumer = KafkaConsumer(
                TOPIC_IN,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id="parsing-service",
                value_deserializer=lambda v: json.loads(v.decode()),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
        except Exception as e:
            log.warning("kafka consumer unavailable, retrying: %s", e)
            time.sleep(5)
            continue
        try:
            for msg in consumer:
                try:
                    handle_event(dict(msg.value))
                except Exception:
                    log.exception("failed to handle %s", msg.value)
        except Exception:
            log.exception("consumer loop died, reconnecting")
            time.sleep(5)


def start_background() -> None:
    global _thread
    if _thread is not None:
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="parsing-consumer")
    _thread.start()
