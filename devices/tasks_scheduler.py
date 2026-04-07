# devices/tasks_scheduler.py (DEPRECATED - Use Django Management Commands)
# NOTE: All Celery task decorators removed
# Use: python manage.py rollup_* instead

# from celery import shared_task  # REMOVED
from django.utils import timezone
from datetime import timedelta
from devices import models
from devices.models import CommandQueue, CommandState
from devices.tasks import process_command_delivery

def command_maintenance_worker():
    now = timezone.now()

    # 1. TTL Cleanup: Expire stale commands efficiently via indexed query
    CommandQueue.objects.filter(
        status__in=[CommandState.PENDING, CommandState.QUEUED, CommandState.DELIVERED],
        expires_at__lte=now
    ).update(status=CommandState.EXPIRED, updated_at=now)

    # 2. Unacknowledged Retry Sweeper
    # Find commands delivered > 5 minutes ago but never acknowledged
    stale_delivered = CommandQueue.objects.filter(
        status=CommandState.DELIVERED,
        updated_at__lte=now - timedelta(minutes=5),
        retry_count__lt=models.F('max_retries')
    )

    for command in stale_delivered:
        command.status = CommandState.PENDING
        command.retry_count += 1
        command.save(update_fields=['status', 'retry_count', 'updated_at'])
        
        # Re-queue to Redis
        process_command_delivery.delay(command.id)
        
    # Mark failed if max retries exceeded
    CommandQueue.objects.filter(
        status=CommandState.DELIVERED,
        updated_at__lte=now - timedelta(minutes=5),
        retry_count__gte=models.F('max_retries')
    ).update(status=CommandState.FAILED, updated_at=now)