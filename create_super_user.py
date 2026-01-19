import os
import django
from django.db.models import Q

# 1. Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings") 
django.setup()

from django.contrib.auth import get_user_model

def create_admin():
    User = get_user_model()
    
    # 2. Get credentials
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    if not all([username, email, password]):
        print("⚠️ Admin credentials not found in environment. Skipping creation.")
        return

    # 3. Check for EITHER username OR email existence
    if User.objects.filter(Q(username=username) | Q(email=email)).exists():
        print(f"ℹ️ Admin account already exists (Username: {username} or Email: {email}). Skipping.")
    else:
        print(f"🛠️ Creating superuser: {username}")
        try:
            User.objects.create_superuser(username=username, email=email, password=password)
            print("✅ Superuser created successfully.")
        except Exception as e:
            print(f"❌ Failed to create superuser: {e}")

if __name__ == "__main__":
    create_admin()