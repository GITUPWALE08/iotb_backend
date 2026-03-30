import requests
import time
import random
import math
from datetime import datetime, timezone

# --- CONFIGURATION ---
INGEST_URL = "http://127.0.0.1:8000/api/telemetry/ingest/" # Update with your actual URL path

DEVICE_ID = "your-device-uuid-here"
# IMPORTANT: Provide the RAW API Key here. Your Django view will hash it automatically.
API_KEY = "your-raw-api-key" 

TEMP_PROPERTY_ID = 1   
MOTOR_PROPERTY_ID = 2  

print(f"🚀 Starting Bulk IoT Simulator for Device: {DEVICE_ID}")
print("Press Ctrl+C to stop.")

tick = 0
while True:
    try:
        # Generate organic, noisy data
        base_temp = 45.0
        temp_value = base_temp + (math.sin(tick * 0.1) * 5) + random.uniform(-0.5, 0.5)
        motor_state = 1 if random.random() > 0.8 else 0

        # Create a "Bulk" payload tailored exactly to your DataIngestionView
        payload = {
            "device_id": DEVICE_ID,
            "api_key": API_KEY,
            "data": [
                {
                    "property": TEMP_PROPERTY_ID,
                    "label": "temperature",
                    "value": round(temp_value, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                {
                    "property": MOTOR_PROPERTY_ID,
                    "label": "motor_status",
                    "value": float(motor_state),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]
        }

        # Fire the bulk payload
        response = requests.post(INGEST_URL, json=payload)
        
        if response.status_code in [202]: # Your view returns 202 ACCEPTED
            print(f"✅ [SUCCESS] Bulk payload queued. (Tick: {tick})")
        else:
            print(f"❌ [FAILED] {response.status_code}: {response.text}")

        tick += 1
        time.sleep(2) # Send bulk data every 2 seconds

    except KeyboardInterrupt:
        print("\n🛑 Simulator stopped.")
        break
    except requests.exceptions.ConnectionError:
        print("⚠️ Connection refused. Is Django running?")
        time.sleep(5)