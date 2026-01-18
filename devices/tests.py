from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from devices.models import Device, User, DeviceCommand
from telemetry.models import TelemetryLog, MediaLog, AlertThreshold
from django.utils import timezone
import hashlib
import uuid

from django.urls import reverse
from django.core import mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient
from rest_framework import status
from .models import User
from .tokens import email_verification_token

User = get_user_model()

class IoTDatabaseIntegrityTest(TestCase):

    def setUp(self):
        """Set up a test user and a test device."""
        self.user = User.objects.create_user(
            username='testengineer',
            password='password123',
            profession='Systems Engineer',
            full_name='John Doe'
        )
        
        self.device = Device.objects.create(
            name="Test Thermal Sensor",
            owner=self.user,
            device_type="Sensor",
            connection_type="HTTPS",
            port_address=443,
            api_key_hash="fake_hash_12345"
        )

    def test_user_creation(self):
        """Test if custom user fields are saved correctly."""
        user = User.objects.get(username='testengineer')
        self.assertEqual(user.profession, 'Systems Engineer')
        self.assertEqual(user.full_name, 'John Doe')

    def test_device_relationship(self):
        """Test if the device is correctly linked to the user."""
        self.assertEqual(self.device.owner.username, 'testengineer')
        self.assertEqual(self.user.devices.count(), 1)

    def test_telemetry_logging(self):
        """Test if numerical telemetry can be saved and retrieved."""
        log = TelemetryLog.objects.create(
            device=self.device,
            label='temperature',
            value=25.6,
            timestamp=timezone.now()
        )
        self.assertEqual(TelemetryLog.objects.count(), 1)
        self.assertEqual(log.device.name, "Test Thermal Sensor")

    def test_metadata_json_field(self):
        """Test if the JSONField supports flexible metadata."""
        self.device.metadata = {"firmware": "v1.0.2", "battery": 85}
        self.device.save()
        
        updated_device = Device.objects.get(id=self.device.id)
        self.assertEqual(updated_device.metadata['firmware'], "v1.0.2")


class IoTSystemDeepTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='admin_eng', password='password')
        self.device = Device.objects.create(
            name="HVAC Controller",
            owner=self.user,
            api_key_hash="hashed_secret_key"
        )

    # --- 1. MEDIA HANDLING TEST ---
    def test_media_file_upload_logic(self):
        """Test if the system can 'store' a video file path correctly."""
        # Create a fake video file in memory
        fake_video = SimpleUploadedFile(
            "engine_fault.mp4", 
            b"file_content_here", 
            content_type="video/mp4"
        )
        
        media_entry = MediaLog.objects.create(
            device=self.device,
            file_type='VIDEO',
            file=fake_video,
            timestamp=timezone.now()
        )
        
        self.assertEqual(MediaLog.objects.count(), 1)
        self.assertTrue(media_entry.file.name.endswith(".mp4"))
        # Verify it's organized by date as per our 'upload_to' setting
        self.assertIn('iot_media', media_entry.file.name)

    # --- 2. ALERT THRESHOLD TEST ---
    def test_alert_threshold_logic(self):
        """Test if alert settings are saved correctly."""
        alert = AlertThreshold.objects.create(
            device=self.device,
            parameter='temperature',
            min_value=10.0,
            max_value=85.0,
            is_active=True
        )
        self.assertEqual(alert.max_value, 85.0)
        self.assertTrue(alert.is_active)

    # --- 3. DATA BULK INTEGRITY TEST ---
    def test_high_frequency_log_sequence(self):
        """Simulate a burst of 100 readings to check performance."""
        batch = []
        for i in range(100):
            batch.append(TelemetryLog(
                device=self.device,
                label='voltage',
                value=220.0 + i,
                timestamp=timezone.now()
            ))
        TelemetryLog.objects.bulk_create(batch)
        self.assertEqual(TelemetryLog.objects.filter(label='voltage').count(), 100)

    # --- 4. SECURITY / ORPHAN TEST ---
    def test_prevent_unowned_device_access(self):
        """Ensure a device must always have an owner."""
        with self.assertRaises(Exception):
            Device.objects.create(name="Rogue Device") # Should fail: no owner


class SecurityLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='security_pro', password='password')
        self.raw_key = "device_secret_123"
        self.hashed_key = hashlib.sha256(self.raw_key.encode()).hexdigest()
        
        self.device = Device.objects.create(
            name="Secure Sensor",
            owner=self.user,
            api_key_hash=self.hashed_key
        )

    def test_api_key_verification(self):
        """Test if we can manually verify a key sent by a device."""
        incoming_key = "device_secret_123"
        incoming_hash = hashlib.sha256(incoming_key.encode()).hexdigest()
        
        # Check if hash matches what's in DB
        self.assertEqual(incoming_hash, self.device.api_key_hash)
        
        # Test a wrong key
        wrong_key = "wrong_password"
        wrong_hash = hashlib.sha256(wrong_key.encode()).hexdigest()
        self.assertNotEqual(wrong_hash, self.device.api_key_hash)


class TelemetryValidationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='eng_1', password='password')
        self.device = Device.objects.create(name="Pressure Valve", owner=self.user)

    def test_negative_values(self):
        """Test if the database handles negative sensor readings (e.g., -20°C)."""
        log = TelemetryLog.objects.create(
            device=self.device,
            label='temp',
            value=-25.5,
            timestamp=timezone.now()
        )
        self.assertEqual(log.value, -25.5)

    def test_large_numerical_value(self):
        """Test handling of very high precision numbers."""
        huge_val = 123456.789012
        log = TelemetryLog.objects.create(
            device=self.device,
            label='precision_sensor',
            value=huge_val,
            timestamp=timezone.now()
        )
        # We use assertAlmostEqual for floats to avoid tiny rounding differences
        self.assertAlmostEqual(log.value, huge_val, places=5)

class CommandSystemTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='password')
        self.device = Device.objects.create(name="Motor A1", owner=self.user)

    def test_command_status_lifecycle(self):
        """Test the lifecycle of a device command."""
        cmd = DeviceCommand.objects.create(
            device=self.device,
            command_name="START_MOTOR",
            payload={"speed": 500}
        )
        self.assertEqual(cmd.status, 'PENDING')
        
        # Simulate device fetching the command
        cmd.status = 'SENT'
        cmd.save()
        
        updated_cmd = DeviceCommand.objects.get(id=cmd.id)
        self.assertEqual(updated_cmd.status, 'SENT')

class UserAuthVerificationTest(TestCase):
    """
    Validates the Production User Flow:
    1. Registration creates an INACTIVE user.
    2. An email is sent with a valid token.
    3. Login is REJECTED before verification.
    4. Activation link makes the user ACTIVE.
    """

    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.user_data = {
            "username": "tester_eng",
            "email": "test@engineering.com",
            "password": "SecurePassword123!",
            "profession": "Automation Engineer",
            "full_name": "Test User"
        }

    def test_full_registration_and_activation_cycle(self):
        # 1. Register User
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(username="tester_eng")
        
        # Verify user is NOT active yet
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)

        # 2. Check if Email was "sent" (captured in console)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verify your IIoT Bridge Account", mail.outbox[0].subject)

        # 3. Attempt Login (Should fail because is_active=False)
        login_data = {"username": "tester_eng", "password": "SecurePassword123!"}
        login_res = self.client.post(self.login_url, login_data, format='json')
        # SimpleJWT returns 401 for inactive users
        self.assertEqual(login_res.status_code, status.HTTP_401_UNAUTHORIZED)

        # 4. Simulate Activation (Using the Token logic)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        activate_url = reverse('activate-account', kwargs={'uidb64': uid, 'token': token})
        
        activate_res = self.client.get(activate_url)
        self.assertEqual(activate_res.status_code, status.HTTP_200_OK)

        # 5. Verify User is now Active
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

        # 6. Final Test: Login should now work
        final_login_res = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(final_login_res.status_code, status.HTTP_200_OK)
        self.assertIn('access', final_login_res.data)