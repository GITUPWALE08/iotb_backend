import json
from django_redis import get_redis_connection

redis_conn = get_redis_connection("default")

def enqueue_mqtt_command(command_id):
    redis_conn.lpush("mqtt_command_queue", command_id)