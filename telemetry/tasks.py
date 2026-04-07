# telemetry/tasks.py (DEPRECATED - Use Django Management Commands)
# NOTE: All Celery task decorators removed
# Use: python manage.py rollup_raw_to_1m instead

from django.utils import timezone
from datetime import timedelta

# Legacy functions kept for reference only
def test_task():
    print("Django management commands are working")

def task_rollup_raw_to_1m():
    # Use: python manage.py rollup_raw_to_1m
    print("Use Django management command instead")
    
def task_rollup_1m_to_5m():
    # Use: python manage.py rollup_1m_to_5m
    print("Use Django management command instead")
    
def task_rollup_5m_to_1h():
    # Use: python manage.py rollup_5m_to_1h
    print("Use Django management command instead")
    
def task_rollup_1h_to_1d():
    # Use: python manage.py rollup_1h_to_1d
    print("Use Django management command instead")

print("Celery tasks deprecated - use Django management commands")