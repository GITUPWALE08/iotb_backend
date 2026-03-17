# import paho.mqtt.client as mqtt
# import json
# from telemetry.models import TelemetryLog
# from devices.models import Device


# def on_message(client, userdata, msg):
#     payload = json.loads(msg.payload.decode())
#     device_id = payload.get('device_id')
#     api_key = payload.get('api_key')
    
#     # 🚨 SECURITY FIX: Hash the key to match DataIngestionView logic
#     key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else ""

#     try:
#         # Validate against the HASH, not just the ID
#         device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
        
#         TelemetryLog.objects.create(
#             device=device,
#             label=payload.get('label'),
#             value=payload.get('value'),
#             timestamp=payload.get('timestamp')
#         )
#         print(f"✅ MQTT Data saved for {device.name}")
#     except Device.DoesNotExist:
#         print(f"❌ BLOCKING unauthorized MQTT attempt for Device {device_id}")
#     except Exception as e:
#         print(f"⚠️ MQTT Error: {e}")


# telemetry/mqtt_bridge.py
import json
import paho.mqtt.client as mqtt
import hashlib
from devices.models import Device
from telemetry.queue import push_to_queue

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        device_id = payload.get("device_id")
        api_key = payload.get("api_key")
        
        if not device_id or not api_key:
            return

        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        
        # Authenticate
        if not Device.objects.filter(id=device_id, api_key_hash=key_hash, is_active=True).exists():
            return
            
        # Push to common Redis queue
        push_to_queue(payload)
        
    except Exception as e:
        print(f"MQTT Error: {e}")



# Setup the listener
client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("iot/sensors/#")
client.loop_forever()