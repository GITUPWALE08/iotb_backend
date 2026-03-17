# telemetry/parsers.py
from datetime import datetime, timezone, timedelta

def parse_gateway_schema(device_id: str, raw_payload: dict, property_map: dict) -> list:
    """
    Parses the optimized gateway schema into dictionaries ready for TelemetryLog.
    Requires a pre-fetched property_map {(device_id, label): property_id} to avoid N+1.
    """
    base_time_ms = raw_payload.get("base_time")
    data_dict = raw_payload.get("data", {})
    
    if not base_time_ms or not data_dict:
        return []

    base_dt = datetime.fromtimestamp(base_time_ms / 1000.0, tz=timezone.utc)
    parsed_records = []

    for label, points in data_dict.items():
        prop_id = property_map.get((str(device_id), label))
        if not prop_id:
            continue # Drop telemetry if the property is not defined in the Digital Twin

        for point in points:
            offset_ms = point[0]
            value = float(point[1])
            timestamp = base_dt + timedelta(milliseconds=offset_ms)
            
            parsed_records.append({
                "device_id": device_id,
                "label": label,
                "value": value,
                "property_id_id": prop_id,
                "timestamp": timestamp
            })
            
    return parsed_records