# telemetry/workers/indicator_engine.py
import json
import redis
from django.conf import settings
from django.db import connection
from telemetry.indicators.registry import registry
from telemetry.models import TelemetryRollup1Min

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class IndicatorEngineWorker:
    
    @classmethod
    def get_state_key(cls, resolution, device_id, property_id):
        return f"ind_state:{resolution}:{device_id}:{property_id}"

    @classmethod
    def process_batch(cls, resolution: str, source_model, target_table: str, start_time, end_time):
        """
        Processes new rollups and computes indicators incrementally.
        """
        # 1. Fetch newly rolled-up candles ordered chronologically
        new_candles = source_model.objects.filter(
            bucket__gte=start_time,
            bucket__lt=end_time
        ).order_by('bucket').values('device_id', 'property_id', 'bucket', 'open', 'high', 'low', 'close', 'volume')

        if not new_candles:
            return

        # Group by device/property to process sequential streams
        streams = {}
        for c in new_candles:
            key = (str(c['device_id']), str(c['property_id']))
            if key not in streams:
                streams[key] = []
            streams[key].append(c)

        execution_plan = registry.get_execution_plan()
        upsert_data = []

        # 2. Process each device/property stream
        for (dev_id, prop_id), candles in streams.items():
            state_key = cls.get_state_key(resolution, dev_id, prop_id)
            
            # Load indicator state from Redis
            raw_state = redis_client.get(state_key)
            state_store = json.loads(raw_state) if raw_state else {}

            for candle in candles:
                indicator_results = {}
                
                # Execute DAG in topological order
                for indicator in execution_plan:
                    ind_state = state_store.get(indicator.name, {})
                    
                    val, new_state = indicator.compute(candle, ind_state, indicator_results)
                    
                    if val is not None:
                        indicator_results[indicator.name] = val
                    state_store[indicator.name] = new_state
                
                # Prepare bulk UPSERT payload
                upsert_data.append((
                    dev_id, prop_id, candle['bucket'], json.dumps(indicator_results)
                ))

            # Save updated state back to Redis
            redis_client.set(state_key, json.dumps(state_store))

        # 3. Bulk UPSERT JSONB results into PostgreSQL
        cls._bulk_upsert(target_table, upsert_data)

    @classmethod
    def _bulk_upsert(cls, target_table, upsert_data):
        query = f"""
            INSERT INTO {target_table} (device_id, property_id, bucket, indicators)
            VALUES %s
            ON CONFLICT (device_id, property_id, bucket) 
            DO UPDATE SET indicators = EXCLUDED.indicators;
        """
        from psycopg2.extras import execute_values
        with connection.cursor() as cursor:
            execute_values(cursor, query, upsert_data)