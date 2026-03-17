from telemetry.models import (
    TelemetryRollup1Min, 
    TelemetryRollup5Min, 
    TelemetryRollup1Hour, 
    TelemetryRollup1Day
)

# Assuming you placed the indicator models in a separate file as designed
from .models_indicator import (
    IndicatorResult1Min, 
    IndicatorResult5Min, 
    IndicatorResult1Hour, 
    IndicatorResult1Day
)

def get_rollup_model(resolution_key: str):
    """Maps a resolution string to the corresponding Rollup Django Model."""
    mapping = {
        "1m": TelemetryRollup1Min,
        "5m": TelemetryRollup5Min,
        "1h": TelemetryRollup1Hour,
        "1d": TelemetryRollup1Day
    }
    # Fallback to 1m if somehow an invalid key is passed
    return mapping.get(resolution_key, TelemetryRollup1Min)

def get_indicator_model(resolution_key: str):
    """Maps a resolution string to the corresponding Indicator Django Model."""
    mapping = {
        "1m": IndicatorResult1Min,
        "5m": IndicatorResult5Min,
        "1h": IndicatorResult1Hour,
        "1d": IndicatorResult1Day
    }
    # Fallback to 1m if somehow an invalid key is passed
    return mapping.get(resolution_key, IndicatorResult1Min)

