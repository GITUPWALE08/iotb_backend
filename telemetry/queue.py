# telemetry/queue.py
import json
import redis
from django.conf import settings
import os

redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

# Initialize strict Redis client
redis_client = redis.from_url(
    redis_url,
    decode_responses=True
)

TELEMETRY_QUEUE_KEY = "iotb:ingest:telemetry_queue"
DLQ_KEY = "iotb:ingest:dead_letter_queue"

def push_to_queue(payload_dict: dict):
    """Pushes authenticated payload to Redis."""
    redis_client.lpush(TELEMETRY_QUEUE_KEY, json.dumps(payload_dict))

def push_to_dlq(payload_dict: dict, error_msg: str):
    """Routes failed payloads for debugging."""
    redis_client.lpush(DLQ_KEY, json.dumps({
        "error": error_msg,
        "payload": payload_dict
    }))
    