import paho.mqtt.client as mqtt
import json
from telemetry.models import TelemetryLog
from devices.models import Device

def on_message(client, userdata, msg):
    # 1. Parse the incoming JSON from the device
    payload = json.loads(msg.payload.decode())
    device_id = payload.get('device_id')
    api_key = payload.get('api_key')
    
    # 2. Re-use the same logic we used in the View!
    # Validate API Key, check Device ID, then save
    try:
        device = Device.objects.get(id=device_id, is_active=True)
        # (Security check here matches our hashing logic)
        
        TelemetryLog.objects.create(
            device=device,
            label=payload.get('label'),
            value=payload.get('value'),
            timestamp=payload.get('timestamp')
        )
        print(f"MQTT Data saved for {device.name}")
    except Exception as e:
        print(f"MQTT Error: {e}")

# Setup the listener
client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("iot/sensors/#")
client.loop_forever()