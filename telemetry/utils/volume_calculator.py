# telemetry/utils/volume_calculator.py
from django.db.models import Avg

def calculate_dynamic_volume(queryset, device_property, interval_seconds: int) -> float:
    """
    Dynamically calculates the chart volume for a time bucket based on device metadata.
    """
    if not queryset.exists():
        return 0.0

    throughput_units = ['L/s', 'L/min', 'm3/s', 'W', 'kW', 'Wh', 'kWh']

    # RULE 1: Physical Throughput
    if device_property.unit in throughput_units:
        avg_val = queryset.aggregate(Avg('value'))['value__avg'] or 0.0
        return float(avg_val * interval_seconds)

    # RULE 2: Binary / State
    elif device_property.data_type == 'BINARY':
        # Retrieve ordered values to calculate absolute differences
        values = list(queryset.values_list('value', flat=True).order_by('timestamp'))
        if len(values) < 2:
            return 0.0
        return float(sum(abs(values[i] - values[i-1]) for i in range(1, len(values))))

    # RULE 3: Default Numerical / High-Frequency
    else:
        return float(queryset.count())