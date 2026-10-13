"""Worker: resume.parsed + job.created -> embedding index."""

import logging
import os
import threading

log = logging.getLogger("embedding-worker")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
_thread: threading.Thread | None = None


def handle_resume_parsed(event: dict) -> int:
    from .db import SessionLocal
    from .pipeline import fetch_parsed_resume, index_resume

    resume_id = event["resume_id"]
    db = SessionLocal()
    try:
        resume = fetch_parsed_resume(resume_id)
        if not resume.get("parsed"):
            log.info("resume %s has no parsed output yet, skipping", resume_id)
            return 0
        return index_resume(db, resume_id, resume["parsed"])
    finally:
        db.close()


def handle_job_created(event: dict) -> str:
    from .db import SessionLocal
    from .pipeline import fetch_job, index_job

    db = SessionLocal()
    try:
        return index_job(db, fetch_job(event["job_id"]))
    finally:
        db.close()


def _loop() -> None:
    import json

    try:
        from kafka import KafkaConsumer
        consumer = KafkaConsumer(
            "resume.parsed",
            "job.created",
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="embedding-service",
            value_deserializer=lambda v: json.loads(v.decode()),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
    except Exception as e:
        log.warning("kafka consumer unavailable, worker idle: %s", e)
        return
    for msg in consumer:
        try:
            if msg.topic == "resume.parsed":
                handle_resume_parsed(dict(msg.value))
            elif msg.topic == "job.created":
                handle_job_created(dict(msg.value))
        except Exception:
            log.exception("failed to handle %s %s", msg.topic, msg.value)


def start_background() -> None:
    global _thread
    if _thread is not None:
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="embedding-consumer")
    _thread.start()
