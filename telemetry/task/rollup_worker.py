# telemetry/tasks/rollup_worker.py
from datetime import timedelta
from django.utils.timezone import now
from django.db import transaction
from celery import shared_task # Ensure these are registered as Celery tasks

from devices.models import DeviceProperty
from telemetry.models import (
    TelemetryLog, 
    TelemetryRollup1Min, 
    TelemetryRollup5Min, 
    TelemetryRollup1Hour, 
    TelemetryRollup1Day
)
from telemetry.utils.volume import calculate_volume
from utils.volume_calculator import calculate_dynamic_volume

@shared_task
def generate_1m_rollups():
    """Runs every minute to aggregate the previous minute's raw data."""
    end_time = now().replace(second=0, microsecond=0)
    start_time = end_time - timedelta(minutes=1)

    properties = DeviceProperty.objects.all()
    
    for prop in properties:
        raw_data = TelemetryLog.objects.filter(
            property_id=prop.id,
            timestamp__gte=start_time,
            timestamp__lt=end_time
        ).order_by('timestamp')
        
        if not raw_data.exists():
            continue

        # Convert to list to iterate safely without locking the DB
        data_list = list(raw_data)
        
        # OHLC Calculation
        open_val = data_list[0].value
        close_val = data_list[-1].value
        high_val = max(d.value for d in data_list)
        low_val = min(d.value for d in data_list)
        
        # Dynamic Volume Calculation
        volume = calculate_dynamic_volume(data_list, prop, interval_seconds=60)
        
        TelemetryRollup1Min.objects.create(
            device_id=prop.device_id,
            label=prop.identifier,
            bucket=start_time,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            volume=volume
        )

@shared_task
def generate_5m_rollups():
    """Runs every 5 minutes to aggregate the previous five 1-minute rollups."""
    end_time = now().replace(second=0, microsecond=0)
    # Snap to the nearest 5-minute boundary strictly (e.g., 10:05, 10:10)
    end_time = end_time.replace(minute=(end_time.minute // 5) * 5)
    start_time = end_time - timedelta(minutes=5)

    properties = DeviceProperty.objects.all()
    
    for prop in properties:
        # Hierarchical rollup: query the 1-minute table instead of the raw logs
        rollup_data = TelemetryRollup1Min.objects.filter(
            device_id=prop.device_id,
            label=prop.identifier,
            bucket__gte=start_time,
            bucket__lt=end_time
        ).order_by('bucket')
        
        if not rollup_data.exists():
            continue

        data_list = list(rollup_data)
        
        # Hierarchical OHLC Calculation
        open_val = data_list[0].open
        close_val = data_list[-1].close
        high_val = max(d.high for d in data_list)
        low_val = min(d.low for d in data_list)
        volume = sum(d.volume for d in data_list)
        
        TelemetryRollup5Min.objects.create(
            device_id=prop.device_id,
            label=prop.identifier,
            bucket=start_time,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            volume=volume
        )

@shared_task
def generate_1h_rollups():
    """Runs every hour to aggregate the previous twelve 5-minute rollups."""
    # Snap to the top of the hour
    end_time = now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=1)

    properties = DeviceProperty.objects.all()
    
    for prop in properties:
        rollup_data = TelemetryRollup5Min.objects.filter(
            device_id=prop.device_id,
            label=prop.identifier,
            bucket__gte=start_time,
            bucket__lt=end_time
        ).order_by('bucket')
        
        if not rollup_data.exists():
            continue

        data_list = list(rollup_data)
        
        # Hierarchical OHLC Calculation
        open_val = data_list[0].open
        close_val = data_list[-1].close
        high_val = max(d.high for d in data_list)
        low_val = min(d.low for d in data_list)
        volume = sum(d.volume for d in data_list)
        
        TelemetryRollup1Hour.objects.create(
            device_id=prop.device_id,
            label=prop.identifier,
            bucket=start_time,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            volume=volume
        )

@shared_task
def generate_1d_rollups():
    """Runs every day to aggregate the previous twenty-four 1-hour rollups."""
    # Snap to midnight
    end_time = now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=1)

    properties = DeviceProperty.objects.all()
    
    for prop in properties:
        rollup_data = TelemetryRollup1Hour.objects.filter(
            device_id=prop.device_id,
            label=prop.identifier,
            bucket__gte=start_time,
            bucket__lt=end_time
        ).order_by('bucket')
        
        if not rollup_data.exists():
            continue

        data_list = list(rollup_data)
        
        # Hierarchical OHLC Calculation
        open_val = data_list[0].open
        close_val = data_list[-1].close
        high_val = max(d.high for d in data_list)
        low_val = min(d.low for d in data_list)
        volume = sum(d.volume for d in data_list)
        
        TelemetryRollup1Day.objects.create(
            device_id=prop.device_id,
            label=prop.identifier,
            bucket=start_time,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            volume=volume
        )