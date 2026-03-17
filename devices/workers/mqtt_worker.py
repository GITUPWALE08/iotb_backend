import json
import time
import paho.mqtt.publish as publish
from django_redis import get_redis_connection
from devices.models import CommandQueue

redis_conn = get_redis_connection("default")

def mqtt_worker():

    while True:

        result = redis_conn.brpop("mqtt_command_queue", timeout=5)

        if not result:
            continue

        _, command_id = result

        try:

            cmd = CommandQueue.objects.select_related(
                "device", "target_property"
            ).get(id=int(command_id))

            topic = f"iot/commands/{cmd.device.id}"

            payload = {
                "command_id": cmd.id,
                "identifier": cmd.target_property.identifier,
                "target_value": cmd.target_value
            }

            publish.single(topic, payload=json.dumps(payload), hostname="localhost", port=1883)

            cmd.status = "DELIVERED"
            cmd.save(update_fields=["status"])

        except Exception:
            cmd.retry_count += 1
            cmd.save(update_fields=["retry_count"])