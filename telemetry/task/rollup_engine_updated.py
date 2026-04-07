# telemetry/task/rollup_engine.py (Updated - No Celery dependencies)

from datetime import datetime
from django.db import connection
from telemetry.queries import SQL_ROLLUP_RAW_TO_1M, SQL_HIERARCHICAL_ROLLUP

class TelemetryRollupEngine:
    
    @staticmethod
    def _execute_sql(query: str, start_time: datetime, end_time: datetime):
        # Force fresh connection to avoid Django SQL cache issues
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(query, [start_time, end_time])
            
    @classmethod
    def execute_raw_to_1m(cls, start_time: datetime, end_time: datetime):
        """Processes massive raw telemetry arrays into 1-minute OHLCV buckets."""
        cls._execute_sql(SQL_ROLLUP_RAW_TO_1M, start_time, end_time)

    @classmethod
    def execute_hierarchical(cls, source_table: str, target_table: str, bin_func: str, start_time: datetime, end_time: datetime):
        """Cascades lower-tier rollups into higher-tier rollups safely."""
        query = SQL_HIERARCHICAL_ROLLUP.format(
            source_table=source_table,
            target_table=target_table,
            time_bin_function=bin_func
        )
        cls._execute_sql(query, start_time, end_time)

    @classmethod
    def execute_1m_to_5m(cls, start_time: datetime, end_time: datetime):
        """Roll up 1-minute data to 5-minute buckets."""
        bin_func = "date_bin('5 minutes', bucket, TIMESTAMP '2000-01-01 00:00:00')"
        cls.execute_hierarchical('telemetry_rollup_1m', 'telemetry_rollup_5m', bin_func, start_time, end_time)

    @classmethod
    def execute_5m_to_1h(cls, start_time: datetime, end_time: datetime):
        """Roll up 5-minute data to 1-hour buckets."""
        bin_func = "date_trunc('hour', bucket)"
        cls.execute_hierarchical('telemetry_rollup_5m', 'telemetry_rollup_1h', bin_func, start_time, end_time)

    @classmethod
    def execute_1h_to_1d(cls, start_time: datetime, end_time: datetime):
        """Roll up 1-hour data to 1-day buckets."""
        bin_func = "date_trunc('day', bucket)"
        cls.execute_hierarchical('telemetry_rollup_1h', 'telemetry_rollup_1d', bin_func, start_time, end_time)

# NOTE: This class is now completely independent of Celery
# It can be safely used by Django management commands and HTTP views
