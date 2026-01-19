import os
import django

# 1. Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings") # Change 'core' to your project folder name if different
django.setup()

from django.contrib.auth import get_user_model

def create_admin():
    User = get_user_model()
    
    # 2. Get credentials from Environment (Render Dashboard)
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    if not all([username, email, password]):
        print("⚠️ Admin credentials not found in environment. Skipping creation.")
        return

    # 3. Create Superuser if it doesn't exist
    if not User.objects.filter(username=username).exists():
        print(f"🛠️ Creating superuser: {username}")
        User.objects.create_superuser(username=username, email=email, password=password)
        print("✅ Superuser created successfully.")
    else:
        print("ℹ️ Superuser already exists. Skipping.")

if __name__ == "__main__":
    create_admin()