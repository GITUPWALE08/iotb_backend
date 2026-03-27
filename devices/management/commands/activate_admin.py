import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates and force-activates the superuser'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not username or not password:
            self.stdout.write(self.style.ERROR('Missing superuser environment variables!'))
            return

        # 1. Create the user if they don't exist
        if User.objects.filter(username=username).exists():
            admin = User.objects.get(username=username)
            self.stdout.write(f"Superuser '{username}' already exists.")
        else:
            admin = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created successfully."))

        # 2. Force native Django activation
        if not admin.is_active:
            admin.is_active = True
            admin.save()
            self.stdout.write(f"Activated native user: {admin.username}")
            
        self.stdout.write(self.style.SUCCESS('Admin setup complete.'))