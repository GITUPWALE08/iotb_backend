from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


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
    api_key_hash = models.CharField(max_length=128, editable=False)
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
class CommandQueue(models.Model):
    """
    The Mailbox. Tracks commands sent from React to the physical device.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Delivery'),
        ('DELIVERED', 'Delivered to Device'),
        ('EXECUTED', 'Executed & Confirmed'),
        ('FAILED', 'Failed / Timeout'),
        ('CANCELLED', 'Cancelled by User')
    ]
    
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='commands')
    target_property = models.ForeignKey(DeviceProperty, on_delete=models.CASCADE)
    
    # The value the user wants to set (e.g., "75" for fan speed, "1" for valve open)
    # Stored as a string so it can hold numbers, booleans, or text
    target_value = models.CharField(max_length=255) 
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(blank=True, null=True)

    def mark_executed(self):
        """Helper method to close the loop when the device confirms the action."""
        self.status = 'EXECUTED'
        self.executed_at = timezone.now()
        self.save()

    def __str__(self):
        return f"Set {self.target_property.identifier} to {self.target_value} [{self.status}]"