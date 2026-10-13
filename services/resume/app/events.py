import json
import logging
import os

log = logging.getLogger("events")
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
_producer = None


def _producer_or_none():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode(),
            request_timeout_ms=3000,
        )
        return _producer
    except Exception as e:
        log.warning("kafka unavailable, falling back to log: %s", e)
        return None


def publish(topic: str, payload: dict) -> bool:
    p = _producer_or_none()
    if p is None:
        log.info("event %s %s", topic, payload)
        return False
    try:
        p.send(topic, payload).get(timeout=5)
        return True
    except Exception as e:
        log.warning("publish failed: %s", e)
        return False
