from django.db import models
from devices.models import Device, DeviceProperty

# --- 4. TELEMETRY LOG (Numerical Data) ---
# telemetry/models.py
from django.db import models

class TelemetryLog(models.Model):
    device = models.ForeignKey('devices.Device', on_delete=models.CASCADE)
    property = models.ForeignKey(DeviceProperty, on_delete=models.CASCADE)
    label = models.CharField(max_length=50)
    value = models.FloatField()
    timestamp = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'telemetry_telemetrylog'
        models.Index(fields=['property', 'timestamp'])
        # Indexes are handled manually in the migration for the partitioned table
        managed = False 

class AbstractTelemetryRollup(models.Model):
    device_id = models.UUIDField()
    property = models.ForeignKey(DeviceProperty, on_delete=models.CASCADE)
    label = models.CharField(max_length=50)
    bucket = models.DateTimeField()
    
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume = models.FloatField()

    class Meta:
        abstract = True

class TelemetryRollup1Min(AbstractTelemetryRollup):
    class Meta:
        db_table = 'telemetry_rollup_1m'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property', 'bucket'], name='unique_1m_bucket')
        ]
        indexes = [
            models.Index(fields=['device_id', 'property', '-bucket']),
        ]

class TelemetryRollup5Min(AbstractTelemetryRollup):
    class Meta:
        db_table = 'telemetry_rollup_5m'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property', 'bucket'], name='unique_5m_bucket')
        ]
        indexes = [
            models.Index(fields=['device_id', 'property', '-bucket']),
        ]

class TelemetryRollup1Hour(AbstractTelemetryRollup):
    class Meta:
        db_table = 'telemetry_rollup_1h'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property', 'bucket'], name='unique_1h_bucket')
        ]
        indexes = [
            models.Index(fields=['device_id', 'property', '-bucket']),
        ]

class TelemetryRollup1Day(AbstractTelemetryRollup):
    class Meta:
        db_table = 'telemetry_rollup_1d'
        constraints = [
            models.UniqueConstraint(fields=['device_id', 'property', 'bucket'], name='unique_1d_bucket')
        ]
        indexes = [
            models.Index(fields=['device_id', 'property', '-bucket']),
        ]

# --- 5. MEDIA LOG (Audio/Video Files) ---
class MediaLog(models.Model):
    MEDIA_TYPES = [('VIDEO', 'Video'), ('AUDIO', 'Audio')]
    
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='media_logs')
    file_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    # File is saved to local disk, DB stores the path
    file = models.FileField(upload_to='iot_media/%Y/%m/%d/')
    timestamp = models.DateTimeField(db_index=True)
    
    def __str__(self):
        return f"{self.file_type} from {self.device.name} at {self.timestamp}"

# --- 6. ALERT CONFIGURATION ---
class AlertThreshold(models.Model):
    """The Watchdog: defines when to notify the engineer."""

    OPERATOR_CHOICES = [
        ('>', 'Greater Than'),
        ('<', 'Less Than'),
        ('=', 'Equals'),
    ]
    NOTIFICATION_CHANNEL_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
    ]
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alerts')
    parameter = models.CharField(max_length=50) # e.g., 'temperature'
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    operator = models.CharField(max_length=1, choices=OPERATOR_CHOICES, default='>')
    notification_channel = models.CharField(
        max_length=10,
        choices=NOTIFICATION_CHANNEL_CHOICES,
        default='EMAIL'
    )
    notification_target = models.CharField(
        max_length=255,
        blank=True,
        help_text='Email address or phone number, depending on notification channel.'
    )
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    cooldown_minutes = models.IntegerField(default=60) 

    def __str__(self):
        return f"Alert: {self.parameter} {self.operator}"
       