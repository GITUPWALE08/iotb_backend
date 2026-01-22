import requests

# --- CONFIGURATION ---
API_KEY = "e65bc3f4887dd6af5cc8686693cddd7d-77c6c375-32072bf0" # <--- PUT YOUR KEY HERE
DOMAIN = "sandboxf8eb86c158ba407aa6cf65c14dee2cb9.mailgun.org"
MY_EMAIL = "princeadewale391@gmail.com"
# ---------------------

def fix_mailgun_eu():
    # 1. Try the EU Endpoint
    base_url = "https://api.eu.mailgun.net/v3"
    list_address = f"sandbox_recipients@{DOMAIN}"
    url = f"{base_url}/lists/{list_address}/members"
    
    print(f"🌍 Connecting to EU Server: {list_address}...")
    
    response = requests.post(
        url,
        auth=("api", API_KEY),
        data={"address": MY_EMAIL, "upsert": "yes"}
    )
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! (You are on the EU Server)")
        print("👉 GO TO YOUR INBOX NOW. Verify the email from Mailgun.")
        return

    # 2. If EU failed, maybe the List is missing? Let's try to CREATE it on US server.
    print(f"⚠️ EU failed ({response.status_code}). Trying to CREATE list on US Server...")
    
    us_base_url = "https://api.mailgun.net/v3"
    create_url = f"{us_base_url}/lists"
    
    # Create the list first
    requests.post(
        create_url,
        auth=("api", API_KEY),
        data={
            "address": list_address,
            "name": "Sandbox Recipients"
        }
    )
    
    # Now try to add member again on US
    us_url = f"{us_base_url}/lists/{list_address}/members"
    response_us = requests.post(
        us_url,
        auth=("api", API_KEY),
        data={"address": MY_EMAIL, "upsert": "yes"}
    )

    if response_us.status_code == 200:
        print("\n✅ SUCCESS! (List was missing, but we created it)")
        print("👉 GO TO YOUR INBOX NOW. Verify the email from Mailgun.")
    else:
        print(f"\n❌ FINAL ERROR: {response_us.status_code}")
        print(response_us.text)

if __name__ == "__main__":
    fix_mailgun_eu()