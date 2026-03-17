# telemetry/utils/volume.py
def calculate_volume(data_list, device_property, interval_seconds):
    """
    Applies the generic IoT volume strategy based on DeviceProperty metadata.
    """
    throughput_units = ['L/s', 'L/min', 'm3/s', 'W', 'kW', 'Wh', 'kWh']
    
    if device_property.unit in throughput_units:
        avg_value = sum(d.value for d in data_list) / len(data_list)
        return avg_value * interval_seconds
        
    elif device_property.data_type == 'BINARY':
        volume = 0.0
        for i in range(1, len(data_list)):
            volume += abs(data_list[i].value - data_list[i-1].value)
        return volume
        
    else:
        return float(len(data_list))