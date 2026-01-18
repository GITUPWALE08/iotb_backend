from django.db import models
from devices.models import Device

# --- 4. TELEMETRY LOG (Numerical Data) ---
class TelemetryLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='telemetry_logs')
    label = models.CharField(max_length=50, db_index=True) # e.g., 'pressure'
    value = models.FloatField()
    
    # Engineering Accuracy: We store the time the device recorded it
    timestamp = models.DateTimeField(db_index=True) 
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            # This index is specifically for "Get data for Device X within Time Y"
            models.Index(fields=['device', 'timestamp']),

            # This index is for filtering by type (e.g., "Show all Temperature sensors")
            models.Index(fields=['label']),
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
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alerts')
    parameter = models.CharField(max_length=50) # e.g., 'temperature'
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)