# telemetry/utils.py
from datetime import datetime, timezone, timedelta
from telemetry.models import TelemetryLog

def unpack_gateway_payload(payload: dict) -> list[TelemetryLog]:
    """
    Unpacks the optimized Columnar Time-Delta schema into Django model instances.
    Compatible with the existing Redis Worker bulk_create logic.
    """
    device_id = payload.get("device_id")
    base_time_ms = payload.get("base_time")
    data_dict = payload.get("data", {})
    
    # Convert base Unix epoch (ms) to aware datetime once per batch
    base_dt = datetime.fromtimestamp(base_time_ms / 1000.0, tz=timezone.utc)
    
    logs_to_create = []
    
    for label, points in data_dict.items():
        for point in points:
            # point is [offset_ms, value, (optional)quality]
            offset_ms = point[0]
            value = point[1]
            
            # Reconstruct exact timestamp
            point_dt = base_dt + timedelta(milliseconds=offset_ms)
            
            logs_to_create.append(
                TelemetryLog(
                    device_id=device_id,
                    label=label,
                    value=value,
                    timestamp=point_dt
                )
            )
            
    return logs_to_create