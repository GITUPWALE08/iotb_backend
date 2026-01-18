import os
import django
import json
import hashlib
import paho.mqtt.client as mqtt

# --- 1. DJANGO SETUP ---
# This allows the script to use Django models outside of the web server
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from telemetry.models import TelemetryLog
from devices.models import Device

# --- 2. MQTT CONFIGURATION ---
MQTT_BROKER = "localhost" # Or broker's IP
MQTT_PORT = 1883
MQTT_TOPIC = "iot/sensors/+" # Subscribes to all sensors

# --- 3. THE LOGIC ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        # Parse the incoming JSON
        data = json.loads(msg.payload.decode())
        
        device_id = data.get('device_id')
        api_key = data.get('api_key') # The raw key from the device
        
        if not device_id or not api_key:
            print("⚠️ Dropping packet: Missing device_id or api_key")
            return

        # Security: Hash the incoming key to match our DB storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Check if device exists and is authorized
        try:
            device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
            
            # Save the Telemetry
            TelemetryLog.objects.create(
                device=device,
                label=data.get('label', 'unknown'),
                value=float(data.get('value', 0)),
                timestamp=data.get('timestamp', django.utils.timezone.now())
            )
            print(f"📊 Saved MQTT data for {device.name}: {data.get('label')}={data.get('value')}")
            
        except Device.DoesNotExist:
            print(f"🚫 Unauthorized: Device {device_id} not found or key invalid")

    except Exception as e:
        print(f"❗ Error processing message: {e}")

# --- 4. START THE BRIDGE ---
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"🚀 Starting MQTT Bridge on {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()