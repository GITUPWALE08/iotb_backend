# telemetry/models_indicators.py
from django.db import models

class AbstractIndicatorResult(models.Model):
    device_id = models.UUIDField()
    property_id = models.BigIntegerField()
    bucket = models.DateTimeField()
    
    # Stores {"SMA_20": 45.2, "EMA_12": 45.1, "RSI_14": 68.5, "MACD_12_26": {"macd": 1.2, "signal": 1.0}}
    indicators = models.JSONField(default=dict)

    class Meta:
        abstract = True

class IndicatorResult1Min(AbstractIndicatorResult):
    class Meta:
        db_table = 'telemetry_indicator_1m'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property_id', 'bucket'], name='uniq_ind_1m')
        ]
        indexes = [models.Index(fields=['device_id', 'property_id', '-bucket'])]

class IndicatorResult5Min(AbstractIndicatorResult):
    class Meta:
        db_table = 'telemetry_indicator_5m'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property_id', 'bucket'], name='uniq_ind_5m')
        ]
        indexes = [models.Index(fields=['device_id', 'property_id', '-bucket'])]

class IndicatorResult1Hour(AbstractIndicatorResult):
    class Meta:
        db_table = 'telemetry_indicator_1h'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property_id', 'bucket'], name='uniq_ind_1h')
        ]
        indexes = [models.Index(fields=['device_id', 'property_id', '-bucket'])]

class IndicatorResult1Day(AbstractIndicatorResult):
    class Meta:
        db_table = 'telemetry_indicator_1d'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property_id', 'bucket'], name='uniq_ind_1d')
        ]
        indexes = [models.Index(fields=['device_id', 'property_id', '-bucket'])]

# (Repeat for 1Hour and 1Day)