import requests
import time
import random

# --- CONFIGURATION ---
BASE_URL = "http://127.0.0.1:8000/api/v1/ingest/"
DEVICE_ID = "f61c5bad-2fa6-4304-980a-d26427f65d33" # Copy from Dashboard Table
API_KEY = "sk_8re1irPs3C0V8Tpt3FG80F4gns6HUMnl" # Copy from Registration Modal
# ---------------------

def simulate_device():
    print(f"🚀 Starting Industrial IoT Agent for {DEVICE_ID}...")
    
    headers = {
        "Content-Type": "application/json",
        # Some industrial gateways send keys in headers, 
        # but our view expects it in the BODY (standard for simple ESP32s)
    }

    while True:
        # 1. Generate Fake Industrial Data
        payload = {
            "device_id": DEVICE_ID,
            "api_key": API_KEY,       # <--- The Critical Security Field
            "label": "pressure",
            "value": round(random.uniform(45.0, 85.0), 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }

        try:
            print(f"📡 Sending: {payload['value']}°C ...", end=" ")
            
            # 2. Hit the "Industrial Ingestion" Endpoint
            response = requests.post(BASE_URL, json=payload, headers=headers)
            
            if response.status_code == 201:
                print("✅ ACK")
            else:
                print(f"❌ FAIL: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"⚠️ Network Error: {e}")

        time.sleep(2) # Send every 2 seconds

if __name__ == "__main__":
    simulate_device()