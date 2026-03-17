# telemetry/utils_optimized.py
from datetime import datetime, timezone
from telemetry.models import TelemetryLog

def unpack_epoch_schema(payload: dict) -> list[TelemetryLog]:
    device_id = payload.get("device_id")
    points = payload.get("points", [])
    
    logs_to_create = []
    
    for point in points:
        # BOTTLENECK RESOLVED: Float division is drastically faster than string parsing
        timestamp = datetime.fromtimestamp(point[2] / 1000.0, tz=timezone.utc)
        
        logs_to_create.append(
            TelemetryLog(
                device_id=device_id,
                label=point[0],
                value=point[1],
                timestamp=timestamp
            )
        )
            
    return logs_to_create