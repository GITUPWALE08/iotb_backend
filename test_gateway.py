import requests
import json
import random
import time
from datetime import datetime

# --- CONFIGURATION ---
# Point this to your local Django server
URL = "http://127.0.0.1:8000/api/v1/ingest/"

# ⚠️ REPLACE THESE WITH YOUR REAL CREDENTIALS
DEVICE_ID = "YOUR_DEVICE_UUID_HERE"  # The ID of the Gateway Device
API_KEY = "sk_YOUR_REAL_KEY_HERE"    # The Gateway's Secret Key

def simulate_gateway_push():
    print(f"🚀 Starting Gateway Simulation for {DEVICE_ID}...")

    # 1. Generate Fake Bulk Data (e.g., 50 readings at once)
    bulk_data = []
    for i in range(50):
        # Simulating different sensors attached to the gateway
        bulk_data.append({
            "label": "temperature",
            "value": round(random.uniform(20.0, 35.0), 2),
            "timestamp": datetime.now().isoformat()
        })
        bulk_data.append({
            "label": "pressure",
            "value": round(random.uniform(1000.0, 1020.0), 2),
            "timestamp": datetime.now().isoformat()
        })

    # 2. Construct the Payload
    # Your views.py looks for a "data" list for bulk uploads
    payload = {
        "device_id": DEVICE_ID,
        "api_key": API_KEY,
        "data": bulk_data  # <--- sending the LIST here
    }

    # 3. Send the POST Request
    try:
        start_time = time.time()
        print(f"📦 Sending {len(bulk_data)} data points...")
        
        response = requests.post(URL, json=payload, headers={"Content-Type": "application/json"})
        
        duration = time.time() - start_time
        
        # 4. Handle Response
        if response.status_code == 201:
            print(f"✅ SUCCESS! Uploaded in {duration:.2f} seconds.")
            print(f"Server Response: {response.json()}")
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"Error Detail: {response.text}")

    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")
        print("Is your Django server running? (python manage.py runserver)")

if __name__ == "__main__":
    simulate_gateway_push()