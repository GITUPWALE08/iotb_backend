# telemetry/tasks/rollup_worker.py
from datetime import timedelta
from django.utils.timezone import now
from django.db import transaction
from devices.models import DeviceProperty
from telemetry.models import TelemetryLog, TelemetryRollup1Min
from telemetry.utils.volume import calculate_volume
from utils.volume_calculator import calculate_dynamic_volume

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