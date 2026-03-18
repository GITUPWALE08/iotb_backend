# telemetry/migrations/0002_partitioned_telemetry.py

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('telemetry', '0001_initial'),
        ('devices', '0001_initial'),
    ]

    operations = [

        migrations.RunSQL(
            sql="""

            DROP TABLE IF EXISTS telemetry_telemetrylog CASCADE;

            CREATE TABLE telemetry_telemetrylog (

                id BIGSERIAL PRIMARY KEY,

                device_id UUID NOT NULL,

                label VARCHAR(50) NOT NULL,

                value DOUBLE PRECISION NOT NULL,

                property_id_id BIGINT NOT NULL,

                timestamp TIMESTAMPTZ NOT NULL,

                received_at TIMESTAMPTZ DEFAULT NOW(),

                PRIMARY KEY (id, timestamp)
                
                CONSTRAINT fk_telemetry_device
                FOREIGN KEY (device_id)
                REFERENCES devices_device(id)
                ON DELETE CASCADE,

                CONSTRAINT fk_telemetry_property
                FOREIGN KEY (property_id_id)
                REFERENCES devices_deviceproperty(id)
                ON DELETE CASCADE

            ) PARTITION BY RANGE (timestamp);


            -- Index optimized for chart queries
            CREATE INDEX ix_telemetry_device_property_ts
            ON telemetry_telemetrylog (device_id, property_id_id, timestamp DESC);


            -- Property analytics
            CREATE INDEX ix_telemetry_property_ts
            ON telemetry_telemetrylog (property_id_id, timestamp DESC);


            -- Time-series scan optimization
            CREATE INDEX ix_telemetry_timestamp_brin
            ON telemetry_telemetrylog USING BRIN (timestamp);


            -- Initial partitions

            CREATE TABLE telemetry_log_y2026m03d14
            PARTITION OF telemetry_telemetrylog
            FOR VALUES FROM ('2026-03-14 00:00:00+00')
            TO ('2026-03-15 00:00:00+00');

            CREATE TABLE telemetry_log_y2026m03d15
            PARTITION OF telemetry_telemetrylog
            FOR VALUES FROM ('2026-03-15 00:00:00+00')
            TO ('2026-03-16 00:00:00+00');

            """,

            reverse_sql="""
            DROP TABLE IF EXISTS telemetry_telemetrylog CASCADE;
            """
        )

    ]