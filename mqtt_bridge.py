import os
import django
import json
import hashlib
import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from devices.models import Device, TelemetryLog, CommandQueue

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
    try:
        # 1. Extract device ID from the topic (e.g., "iot/telemetry/1234-uuid")
        device_id = msg.topic.split('/')[-1]
        device = Device.objects.get(id=device_id)
        
        # 2. Parse the incoming telemetry payload
        payload = json.loads(msg.payload.decode('utf-8'))
        
        print(f"📥 Received data from {device.name}: {payload}")

        # Loop through every data point the device just sent
        for key, value in payload.items():
            
            # --- EXISTING LOGIC: Save the raw telemetry ---
            TelemetryLog.objects.create(
                device=device,
                label=key,
                value=float(value) if isinstance(value, (int, float)) else 0.0 # Adjust based on your current setup
            )

            # --- NEW LOGIC: Close the Control Loop ---
            # Check if there are any commands waiting for this specific property
            pending_commands = CommandQueue.objects.filter(
                device=device,
                target_property__identifier=key,
                status__in=['PENDING', 'DELIVERED']
            )

            for command in pending_commands:
                # Does the device's actual reported value match what the user requested?
                # We convert both to strings to avoid type-mismatch errors (e.g., "1" vs 1)
                if str(value) == str(command.target_value):
                    command.mark_executed() # Uses the helper method we defined in models.py
                    print(f"✅ Loop Closed: Device confirmed '{key}' is now {value}.")
                else:
                    print(f"⏳ Still waiting: Requested {command.target_value}, but device reported {value}.")

    except Device.DoesNotExist:
        print(f"⚠️ Unknown device ID in topic: {msg.topic}")
    except json.JSONDecodeError:
        print(f"⚠️ Invalid JSON payload received: {msg.payload}")
    except Exception as e:
        print(f"❌ Error processing message: {str(e)}")

        
# ... (Standard MQTT Client setup below) ...
client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("iot/sensors/#")
client.loop_forever()