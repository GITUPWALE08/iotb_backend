import os
import django
import json
import hashlib
import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from telemetry.models import TelemetryLog
from devices.models import Device

# Buffering Settings
BUFFER_SIZE = 50 
data_buffer = []

def broadcast_live(device_id, data):
    """Pushes data to the React dashboard instantly via WebSockets"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"device_{device_id}",
        {"type": "live_telemetry", "data": [data]}
    )

def on_message(client, userdata, msg):
    global data_buffer
    try:
        data = json.loads(msg.payload.decode())
        device_id = data.get('device_id')
        api_key = data.get('api_key')
        
        # 1. Quick Security & Validation
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        device = Device.objects.filter(id=device_id, api_key_hash=key_hash, is_active=True).first()
        
        if device:
            # 2. INSTANT BROADCAST (Bypasses DB for speed)
            broadcast_live(device_id, data)

            # 3. BUFFER FOR DB (B-Tree Optimized Saving)
            data_buffer.append(TelemetryLog(
                device=device,
                label=data.get('label'),
                value=data.get('value'),
                timestamp=data.get('timestamp', django.utils.timezone.now())
            ))

            # 4. BULK SAVE (Only when buffer is full)
            if len(data_buffer) >= BUFFER_SIZE:
                TelemetryLog.objects.bulk_create(data_buffer)
                data_buffer = [] # Clear buffer
                print(f"📦 Bulk saved {BUFFER_SIZE} logs to MySQL")

    except Exception as e:
        print(f"❗ MQTT Error: {e}")

# ... (Standard MQTT Client setup below) ...
client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("iot/sensors/#")
client.loop_forever()