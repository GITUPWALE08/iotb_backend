# telemetry/api/queries.py
from collections import defaultdict
from telemetry.utils.downsample import downsample_lttb

def execute_chart_query(model, resolution, device_ids, property_ids, start_time, end_time):
    time_field = 'timestamp' if resolution == 'raw' else 'bucket'
    
    # 1. Fetch raw tuples from PostgreSQL (Extremely fast, bypasses dict creation)
    if resolution == 'raw':
        fields = ('device_id', 'property_id', time_field, 'value')
    else:
        fields = ('device_id', 'property_id', time_field, 'open', 'high', 'low', 'close', 'volume')

    queryset = model.objects.filter(
        device_id__in=device_ids,
        property_id__in=property_ids,
        **{f"{time_field}__gte": start_time},
        **{f"{time_field}__lt": end_time}
    ).order_by('device_id', 'property_id', time_field).values_list(*fields)

    # 2. Pivot into Columnar Multi-Device/Property JSON
    formatted_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    # Grouping logic
    if resolution == 'raw':
        # Temporary structure for LTTB downsampling
        raw_series = defaultdict(lambda: defaultdict(list))
        for dev_id, prop_id, ts, val in queryset:
            raw_series[str(dev_id)][str(prop_id)].append((int(ts.timestamp() * 1000), val))
            
        for dev_id, props in raw_series.items():
            for prop_id, series in props.items():
                sampled = downsample_lttb(series, threshold=50000)
                formatted_data[dev_id][prop_id] = {
                    "timestamps": [p[0] for p in sampled],
                    "values": [p[1] for p in sampled]
                }
    else:
        # OHLCV Rollups (Already compressed, no LTTB needed)
        for dev_id, prop_id, ts, o, h, l, c, v in queryset:
            d_id, p_id = str(dev_id), str(prop_id)
            formatted_data[d_id][p_id]["timestamps"].append(int(ts.timestamp() * 1000))
            formatted_data[d_id][p_id]["open"].append(o)
            formatted_data[d_id][p_id]["high"].append(h)
            formatted_data[d_id][p_id]["low"].append(l)
            formatted_data[d_id][p_id]["close"].append(c)
            formatted_data[d_id][p_id]["volume"].append(v)

    return formatted_data
