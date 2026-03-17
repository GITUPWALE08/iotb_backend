# telemetry/utils/cache.py
import json
from django.core.cache import cache
import hashlib
from telemetry.queue import redis_client

def get_cached_chart_data(device_id, label, start_time, end_time, resolution_key, fetch_callback):
    cache_key = f"chart:{device_id}:{label}:{start_time.timestamp()}:{end_time.timestamp()}:{resolution_key}"
    
    cached_payload = cache.get(cache_key)
    if cached_payload:
        return json.loads(cached_payload)
        
    # Cache miss: Execute DB query callback
    data = fetch_callback()
    
    # Cache for 60 seconds (aligns with the minimum rollup interval)
    cache.set(cache_key, json.dumps(list(data)), timeout=60)
    return data

def get_chart_cache_key(device_id, property_id, resolution):
    # Base key for pattern matching invalidation
    return f"chart_cache:{resolution}:{device_id}:{property_id}"

def invalidate_chart_cache(resolution, device_id, property_id):
    """
    Called at the end of `IndicatorEngineWorker.process_batch`.
    """
    pattern = f"{get_chart_cache_key(device_id, property_id, resolution)}:*"
    # In Redis, SCAN and DELETE keys matching this pattern
    # to force the UI to fetch the newly computed indicators.
    keys_to_delete = redis_client.keys(pattern)
    if keys_to_delete:
        redis_client.delete(*keys_to_delete)

def generate_chart_cache_key(device_ids, property_ids, start_ts, end_ts, resolution):
    # Sort to ensure predictable keys
    dev_str = ",".join(sorted(device_ids))
    prop_str = ",".join(sorted(property_ids))
    
    raw_key = f"{dev_str}:{prop_str}:{start_ts}:{end_ts}:{resolution}"
    # Hash the key to prevent Redis max key length violations on massive multi-device queries
    key_hash = hashlib.md5(raw_key.encode('utf-8')).hexdigest()
    
    return f"chart_api:{resolution}:{key_hash}"

def get_or_set_chart_cache(device_ids, property_ids, start_time, end_time, resolution, ttl, query_callback):
    cache_key = generate_chart_cache_key(
        device_ids, property_ids, 
        int(start_time.timestamp()), int(end_time.timestamp()), 
        resolution
    )
    
    cached_data = cache.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
        
    data = query_callback()
    cache.set(cache_key, json.dumps(data), timeout=ttl)
    return data