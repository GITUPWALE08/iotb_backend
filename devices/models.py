from datetime import timezone
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta

# --- 1. CUSTOM USER ---
class User(AbstractUser):
    """
    Extends base User to include engineering-specific profile data.
    """
    profession = models.CharField(max_length=100, blank=True)
    full_name = models.CharField(max_length=255, blank=True)

    # Verification Fields
    email = models.EmailField(unique=True) # Ensure email is unique for verification
    is_email_verified = models.BooleanField(default=False)
    
    # Set default to False so they must verify email to log in
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.username


# --- 2. DEVICE TABLE ---
class Device(models.Model):
    CONNECTION_CHOICES = [
        ('HTTPS', 'HTTPS'),
        ('MQTT', 'MQTT'),
        ('GATEWAY', 'Gateway'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=100, help_text="e.g., Vibration Sensor, Flow Meter")
    
    # Connection details
    connection_type = models.CharField(max_length=10, choices=CONNECTION_CHOICES, default='HTTPS')
    port_address = models.IntegerField(default=80)
    
    # Security & Status
    api_key_hash = models.CharField(max_length=128, editable=False, )
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)
    
    
    # Flexible metadata (Firmware version, Battery, etc.)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.id} {self.connection_type})"


# --- 3. DEVICE PROPERTIES (Digital Twin Blueprint) ---
class DeviceProperty(models.Model):
    """
    The Digital Twin Blueprint. Defines what the device can read and write.
    """
    PROPERTY_TYPES = [
        ('TELEMETRY', 'Telemetry (Read-Only)'),
        ('COMMAND', 'Command (Write or Read/Write)')
    ]
    
    DATA_TYPES = [
        ('BINARY', 'Binary (On/Off)'),
        ('RANGE', 'Number Range'),
        ('TEXT', 'Text / Enum')
    ]

    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='properties')
    name = models.CharField(max_length=100) # Human readable: e.g., "Main Cooling Fan"
    
    # The exact JSON key the physical device uses (e.g., "fan_speed")
    # This MUST match the `label` saved in your TelemetryLog
    identifier = models.CharField(max_length=100) 
    
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES)
    
    # Metadata for the React UI to render properly
    unit = models.CharField(max_length=20, blank=True, null=True) # e.g., RPM, °C, PSI
    min_value = models.FloatField(blank=True, null=True) # Used if data_type is RANGE
    max_value = models.FloatField(blank=True, null=True) # Used if data_type is RANGE
    
    class Meta:
        # A single device cannot have two properties with the exact same JSON key
        unique_together = ('device', 'identifier') 

    def __str__(self):
        return f"{self.device.name} - {self.name} ({self.property_type})"


# --- 4. COMMAND QUEUE (Mailbox for React -> Device) ---
class CommandState(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    QUEUED = 'QUEUED', 'Queued in Redis'
    DELIVERED = 'DELIVERED', 'Delivered to Device'
    EXECUTED = 'EXECUTED', 'Acknowledged Execution'
    FAILED = 'FAILED', 'Execution Failed'
    CANCELLED = 'CANCELLED', 'Cancelled by User'
    EXPIRED = 'EXPIRED', 'TTL Expired'


class CommandQueue(models.Model):
    id = models.BigAutoField(primary_key=True)
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='commands')
    target_property = models.ForeignKey('DeviceProperty', on_delete=models.CASCADE)
    target_value = models.CharField(max_length=255)
    
    status = models.CharField(max_length=20, choices=CommandState.choices, default=CommandState.PENDING)
    
    # Reliability & Tracking
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=5)
    
    # Timestamps & TTL
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'devices_commandqueue'
        constraints = [
            # Prevents duplicate submissions from the UI or API retries
            models.UniqueConstraint(
                fields=['device', 'idempotency_key'], 
                name='unique_command_idempotency',
                condition=models.Q(idempotency_key__isnull=False)
            )
        ]
        indexes = [
            # Optimized for HTTPS Polling and TTL Sweepers
            models.Index(fields=['device', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24) # Default 24h TTL
        super().save(*args, **kwargs)    
