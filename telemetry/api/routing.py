# telemetry/api/routing.py
from datetime import timedelta
from telemetry.models import TelemetryLog, TelemetryRollup1Min, TelemetryRollup5Min, TelemetryRollup1Hour, TelemetryRollup1Day

def get_rollup_strategy(start_time, end_time):
    """
    Determines the optimal database table and cache TTL based on the time range.
    """
    delta = end_time - start_time
    
    if delta <= timedelta(hours=1):
        return TelemetryLog, 'raw', 1  # 1 second TTL for raw live data
    elif delta <= timedelta(hours=24):
        return TelemetryRollup1Min, '1m', 60  # 60 seconds TTL
    elif delta <= timedelta(days=7):
        return TelemetryRollup5Min, '5m', 300  # 5 mins TTL
    elif delta <= timedelta(days=30):
        return TelemetryRollup1Hour, '1h', 3600  # 1 hour TTL
    else:
        return TelemetryRollup1Day, '1d', 86400  # 1 day TTL