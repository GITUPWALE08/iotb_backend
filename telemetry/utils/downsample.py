# telemetry/utils/downsample.py
import math

def downsample_lttb(data, threshold=50000):
    """
    Largest Triangle Three Buckets (LTTB) Downsampling.
    Preserves visual shape of the chart.
    data format: list of tuples [(timestamp_ms, value), ...]
    """
    data_length = len(data)
    if threshold >= data_length or threshold == 0:
        return data

    sampled = []
    bucket_size = (data_length - 2) / (threshold - 2)
    
    sampled.append(data[0])  # Always include the first point
    a = 0

    for i in range(threshold - 2):
        # Calculate bucket ranges
        bucket_start = math.floor((i + 1) * bucket_size) + 1
        bucket_end = min(math.floor((i + 2) * bucket_size) + 1, data_length)
        
        next_bucket_start = bucket_end
        next_bucket_end = min(math.floor((i + 3) * bucket_size) + 1, data_length)
        
        # Calculate center of next bucket (Average X and Y)
        next_bucket_length = next_bucket_end - next_bucket_start
        if next_bucket_length == 0:
            break
            
        avg_x = sum(data[j][0] for j in range(next_bucket_start, next_bucket_end)) / next_bucket_length
        avg_y = sum(data[j][1] for j in range(next_bucket_start, next_bucket_end)) / next_bucket_length

        # Find max triangle area in current bucket
        max_area = -1
        max_area_point = None
        next_a = 0
        
        point_a_x, point_a_y = data[a][0], data[a][1]
        
        for j in range(bucket_start, bucket_end):
            # Calculate triangle area over the 3 points
            area = abs(
                (point_a_x - avg_x) * (data[j][1] - point_a_y) - 
                (point_a_x - data[j][0]) * (avg_y - point_a_y)
            ) * 0.5
            
            if area > max_area:
                max_area = area
                max_area_point = data[j]
                next_a = j
                
        sampled.append(max_area_point)
        a = next_a

    sampled.append(data[data_length - 1])  # Always include the last point
    return sampled