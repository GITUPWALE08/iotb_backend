from django.utils import timezone
from devices.models import CommandQueue

def timeout_commands():

    timeout_threshold = timezone.now() - timezone.timedelta(minutes=5)

    CommandQueue.objects.filter(
        status='PENDING',
        created_at__lt=timeout_threshold
    ).update(status='FAILED')