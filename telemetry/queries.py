# telemetry/queries.py
#there seems to be error may be due to my using same commit message
# Query 1: Raw Telemetry to 1-Minute Rollup
# Joins with DeviceProperty to apply dynamic Volume rules.
SQL_ROLLUP_RAW_TO_1M = """
WITH raw_data AS (
    SELECT
        t.device_id,
        t.property_id_id AS property_id,
        t.label,
        t.value,
        t.timestamp,
        date_trunc('minute', t.timestamp) AS bucket,
        p.unit,
        p.data_type,
        -- Window function to get previous value for binary state change calculation
        LAG(t.value) OVER (PARTITION BY t.device_id, t.property_id_id ORDER BY t.timestamp) as prev_value
    FROM telemetry_telemetrylog t
    JOIN devices_deviceproperty p ON t.property_id_id = p.id
    WHERE t.timestamp >= %s AND t.timestamp < %s
),
aggregated AS (
    SELECT
        device_id,
        property_id_id,
        MAX(label) AS label,
        bucket,
        -- Use array_agg for highly optimized first/last values within a GROUP BY
        (array_agg(value ORDER BY timestamp ASC))[1] AS open,
        MAX(value) AS high,
        MIN(value) AS low,
        (array_agg(value ORDER BY timestamp DESC))[1] AS close,
        
        -- Dynamic Volume Rules executed inside Postgres
        CASE
            WHEN MAX(unit) IN ('L/s', 'L/min', 'm3/s', 'W', 'kW', 'Wh', 'kWh') THEN AVG(value) * 60.0
            WHEN MAX(data_type) = 'BINARY' THEN SUM(ABS(value - COALESCE(prev_value, value)))
            ELSE COUNT(value)::float
        END AS volume
    FROM raw_data
    GROUP BY device_id, property_id, bucket
)
INSERT INTO telemetry_rollup_1m (device_id, property_id, label, bucket, open, high, low, close, volume)
SELECT device_id, property_id, label, bucket, open, high, low, close, volume FROM aggregated
ON CONFLICT (device_id, property_id, bucket) 
DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume;
"""

# Query 2: Hierarchical Rollup (Lower Tier to Higher Tier)
# Reusable query for 1m->5m, 5m->1h, 1h->1d. Notice volume is simply SUM(volume).
SQL_HIERARCHICAL_ROLLUP = """
WITH aggregated AS (
    SELECT
        device_id,
        property_id,
        MAX(label) AS label,
        {time_bin_function} AS bucket,
        (array_agg(open ORDER BY bucket ASC))[1] AS open,
        MAX(high) AS high,
        MIN(low) AS low,
        (array_agg(close ORDER BY bucket DESC))[1] AS close,
        SUM(volume) AS volume
    FROM {source_table}
    WHERE bucket >= %s AND bucket < %s
    GROUP BY device_id, property_id, {time_bin_function}
)
INSERT INTO {target_table} (device_id, property_id, label, bucket, open, high, low, close, volume)
SELECT device_id, property_id, label, bucket, open, high, low, close, volume FROM aggregated
ON CONFLICT (device_id, property_id, bucket) 
DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume;
"""