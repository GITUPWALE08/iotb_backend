import time
import json
import random
import requests
import paho.mqtt.client as mqtt

# --- CONFIGURATION ---
BASE_URL = "http://127.0.0.1:8000/api/v1/ingest/"
MQTT_BROKER = "localhost"  # Or 'test.mosquitto.org' for public testing
MQTT_PORT = 1883
MQTT_TOPIC = "iot/telemetry"
api_key = "sk_yZjIF0EdBBLFBT8Gd5Icow"

def test_gateway_http(device_id, api_key):
    """
    Simulates a Gateway sending 50 data points in ONE request.
    """
    print(f"\n🚀 Simulating GATEWAY Bulk Upload for {device_id}...")
    
    # Generate 50 fake readings
    bulk_payload = []
    for i in range(50):
        bulk_payload.append({
            "label": "temperature",
            "value": round(random.uniform(20.0, 30.0), 2),
            "timestamp": "2023-10-27T10:00:00Z" # Optional: You can let backend set time
        })

    # Construct the Gateway Packet
    packet = {
        "device_id": device_id,
        "api_key": api_key,
        "data": bulk_payload # List of points
    }

    try:
        start_time = time.time()
        response = requests.post(BASE_URL, json=packet)
        duration = time.time() - start_time
        
        if response.status_code == 201:
            print(f"✅ SUCCESS! Uploaded {len(bulk_payload)} points in {duration:.2f}s")
            print(f"Server Response: {response.json()}")
        else:
            print(f"❌ FAILED: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Connection Error: {e}")

def test_mqtt_publish(device_id, api_key):
    """
    Simulates a device publishing data to an MQTT Broker.
    """
    print(f"\n📡 Simulating MQTT Device for {device_id}...")
    print(f"Target: {MQTT_BROKER}:{MQTT_PORT} -> Topic: {MQTT_TOPIC}/{device_id}")

    client = mqtt.Client()

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        # Simulate sending 5 messages
        for i in range(5):
            payload = {
                "device_id": device_id,
                "api_key": api_key,
                "label": "vibration",
                "value": round(random.uniform(0.1, 5.0), 2)
            }
            
            # Publish to a specific topic for this device
            topic = f"{MQTT_TOPIC}/{device_id}"
            client.publish(topic, json.dumps(payload))
            print(f"➡️ Published: {payload['value']} to {topic}")
            time.sleep(1)
            
        client.loop_stop()
        print("✅ MQTT Test Complete (Check your backend listener!)")

    except Exception as e:
        print(f"❌ MQTT Connection Failed: {e}")
        print("Tip: Do you have an MQTT Broker (like Mosquitto) running?")

if __name__ == "__main__":
    print("--- INDUSTRIAL CONNECTIVITY TESTER ---")
    d_id = input("Enter Device UUID: ").strip()
    d_key = input("Enter API Key (sk_...): ").strip()
    
    print("\nSelect Protocol:")
    print("1. Gateway (HTTP Bulk Upload)")
    print("2. MQTT (Broker Publisher)")
    
    choice = input("Choice (1/2): ")
    
    if choice == "1":
        test_gateway_http(d_id, d_key)
    elif choice == "2":
        test_mqtt_publish(d_id, d_key)
    else:
        print("Invalid choice.")