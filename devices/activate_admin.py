from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Force activates superusers'

    def handle(self, *args, **options):
        User = get_user_model()
        admins = User.objects.filter(is_superuser=True)
        
        for admin in admins:
            # Force native Django activation
            admin.is_active = True
            admin.save()
            self.stdout.write(f"Activated native user: {admin.email}")
                
        self.stdout.write(self.style.SUCCESS('Admin activation complete.'))