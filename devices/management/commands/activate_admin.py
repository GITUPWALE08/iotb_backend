import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Forcefully creates, sets password, and activates the superuser'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Pull from environment, fallback to defaults if env fails
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'iot_admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'princedemytee@gmail.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Iot_password1')

        # 1. Get or Create the user
        admin_user, created = User.objects.get_or_create(
            username=username, 
            defaults={'email': email}
        )

        # 2. Force the password (Bypasses similarity validators)
        admin_user.set_password(password)
        
        # 3. Force all admin permissions and activation
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"User '{username}' created and forced active."))
        else:
            self.stdout.write(self.style.SUCCESS(f"User '{username}' updated: Password forced and activated."))