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
    is_online = models.BooleanField(default=False) # Add this line
    
    # Flexible metadata (Firmware version, Battery, etc.)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.id})"

# --- 3. DEVICE COMMANDS (Control Loop) ---
class DeviceCommand(models.Model):
    """Allows engineers to send instructions BACK to the device."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='commands')
    command_name = models.CharField(max_length=100) # e.g., 'SHUTDOWN', 'RESET'
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default='PENDING', choices=[
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('EXECUTED', 'Executed'),
        ('FAILED', 'Failed'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)