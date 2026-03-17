# telemetry/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from telemetry.tasks.rollup_engine import TelemetryRollupEngine


@shared_task
def test_task():
    print("Celery is working")

@shared_task
def task_rollup_raw_to_1m():
    # Process the last 2 minutes to catch slightly delayed ingestion
    end_time = timezone.now().replace(second=0, microsecond=0)
    start_time = end_time - timedelta(minutes=2)
    TelemetryRollupEngine.execute_raw_to_1m(start_time, end_time)

@shared_task
def task_rollup_1m_to_5m():
    # Process the last 10 minutes from the 1m table
    end_time = timezone.now().replace(second=0, microsecond=0)
    start_time = end_time - timedelta(minutes=10)
    TelemetryRollupEngine.execute_1m_to_5m(start_time, end_time)

@shared_task
def task_rollup_5m_to_1h():
    end_time = timezone.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=2)
    TelemetryRollupEngine.execute_5m_to_1h(start_time, end_time)

@shared_task
def task_rollup_1h_to_1d():
    end_time = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=2)
    TelemetryRollupEngine.execute_1h_to_1d(start_time, end_time)