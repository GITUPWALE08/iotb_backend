# devices/tasks.py
import json
import paho.mqtt.publish as publish
from django.conf import settings
from django.utils import timezone
from devices.models import CommandQueue, CommandState

# NOTE: These functions are now called synchronously, not as Celery tasks
# All command processing happens immediately without background workers

def process_command_delivery(command_id):
    """Process command delivery - now synchronous (no Celery)"""
    try:
        command = CommandQueue.objects.select_related('device', 'target_property').get(id=command_id)
    except CommandQueue.DoesNotExist:
        return

    # Check TTL Expiration
    if timezone.now() > command.expires_at:
        command.status = CommandState.EXPIRED
        command.save(update_fields=['status', 'updated_at'])
        return

    device = command.device

    # --- HTTPS / GATEWAY POLLING ---
    # Devices that poll do not need a push. We mark them QUEUED so they appear in the poll endpoint.
    if device.connection_type in ['HTTPS', 'GATEWAY']:
        command.status = CommandState.QUEUED
        command.save(update_fields=['status', 'updated_at'])
        return

    # --- MQTT PUSH DELIVERY ---
    if device.connection_type == 'MQTT':
        # Offline Protection
        if not device.is_online:
            command.retry_count += 1
            command.save(update_fields=['retry_count'])
            # Exponential backoff: 2s, 4s, 8s, 16s, 32s
            countdown = 2 ** self.request.retries 
            raise self.retry(exc=Exception("Device Offline"), countdown=countdown)

        payload = {
            "cmd_id": command.id,
            "property": command.target_property.identifier,
            "value": command.target_value,
            "exp": int(command.expires_at.timestamp())
        }

        try:
            # Publish with QoS 1 guarantees delivery to the MQTT Broker
            publish.single(
                topic=f"iotb/devices/{device.id}/commands",
                payload=json.dumps(payload),
                qos=1,
                hostname=settings.MQTT_BROKER_URL,
                port=settings.MQTT_BROKER_PORT
            )
            
            # Successfully pushed to broker
            command.status = CommandState.DELIVERED
            command.save(update_fields=['status', 'updated_at'])
            
        except Exception as e:
            command.retry_count += 1
            command.save(update_fields=['retry_count'])
            raise self.retry(exc=e, countdown=2 ** self.request.retries)