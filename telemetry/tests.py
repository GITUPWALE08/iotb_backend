import hashlib
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from devices.models import Device, User
from telemetry.models import TelemetryLog, MediaLog


class IoTSystemFinalTest(TransactionTestCase):
    """
    Detailed system-level validation:
    1. SHA-256 Auth Verification
    2. Atomic Bulk Ingestion (100 rows)
    3. Payload Threshold Guard (Preventing DoS)
    4. Media Storage Integrity
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='eng_admin', password='password123')
        
        # Hardware Setup
        self.raw_key = "iot_secure_key_777"
        self.hashed_key = hashlib.sha256(self.raw_key.encode()).hexdigest()
        
        self.device = Device.objects.create(
            name="Smart Boiler",
            owner=self.user,
            api_key_hash=self.hashed_key,
            is_active=True
        )
        self.data_url = reverse('data-ingest')
        self.media_url = reverse('media-ingest')

    def test_hashing_security_flow(self):
        """Test: Does the server correctly hash the header key and match the DB?"""
        payload = {"device_id": str(self.device.id), "data": [{"label": "psi", "value": 45}]}
        
        # Success Case
        response = self.client.post(self.data_url, payload, format='json', HTTP_X_API_KEY=self.raw_key)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Failure Case: Wrong key
        response = self.client.post(self.data_url, payload, format='json', HTTP_X_API_KEY="wrong_key")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_high_frequency_bulk_save(self):
        """Test: Can the MySQL B-Tree handle a burst of 100 rows safely?"""
        burst_data = [
            {"label": "temp", "value": 25.0 + i, "timestamp": str(timezone.now())}
            for i in range(100)
        ]
        payload = {"device_id": str(self.device.id), "data": burst_data}
        
        response = self.client.post(self.data_url, payload, format='json', HTTP_X_API_KEY=self.raw_key)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TelemetryLog.objects.filter(device=self.device).count(), 100)

    def test_media_type_protection(self):
        """Test: Reject non-file uploads to the media endpoint."""
        data = {"device_id": str(self.device.id), "file_type": "VIDEO"} # Missing the 'file'
        response = self.client.post(self.media_url, data, format='multipart', HTTP_X_API_KEY=self.raw_key)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)



class IoTProductionTest(TransactionTestCase):
    """
    Comprehensive tests for the Industrial IoT Bridge:
    - Verifies SHA-256 Security
    - Verifies Bulk Ingestion Performance
    - Verifies Media Validation logic
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='tester', password='password')
        
        # Security Setup
        self.raw_key = "device_secret_2026"
        self.hashed_key = hashlib.sha256(self.raw_key.encode()).hexdigest()
        
        self.device = Device.objects.create(
            name="Test Turbine",
            owner=self.user,
            api_key_hash=self.hashed_key,
            is_active=True
        )
        self.url = reverse('data-ingest')

    def test_secure_bulk_ingestion(self):
        """Test: Can 100 points be ingested safely in one call?"""
        payload = {
            "device_id": str(self.device.id),
            "data": [
                {"label": "rpm", "value": 1500.0 + i, "timestamp": str(timezone.now())}
                for i in range(100)
            ]
        }
        
        # Using the custom Header we defined
        response = self.client.post(self.url, payload, format='json', HTTP_X_API_KEY=self.raw_key)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TelemetryLog.objects.filter(device=self.device).count(), 100)
        # print(f"\n✅ Bulk Ingestion Passed: 100 points saved in {response.elapsed.total_seconds()}s")

    def test_malicious_payload_size(self):
        """Test: Does the server reject a payload over the 500-point threshold?"""
        oversized_data = [{"label": "err", "value": 0}] * 600
        payload = {"device_id": str(self.device.id), "data": oversized_data}
        
        response = self.client.post(self.url, payload, format='json', HTTP_X_API_KEY=self.raw_key)
        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        print("✅ Payload Threshold Guard: Working.")

    def test_media_file_validation(self):
        """Test: Does the media ingestion handle real binary uploads?"""
        media_url = reverse('media-ingest')
        fake_video = SimpleUploadedFile("clip.mp4", b"content", content_type="video/mp4")
        
        data = {
            "device_id": str(self.device.id),
            "file_type": "VIDEO",
            "file": fake_video,
            "timestamp": timezone.now()
        }
        
        response = self.client.post(media_url, data, format='multipart', HTTP_X_API_KEY=self.raw_key)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(MediaLog.objects.exists())
        print("✅ Media Ingestion Passed: File stored and linked.")

    def test_csv_ingestion(self):
        """Test: Can the server process a CSV file upload as telemetry?"""
        csv_content = "label,value\nvolume,150.0\npressure,200.5"
        csv_file = SimpleUploadedFile("data.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        data = {
            "device_id": str(self.device.id),
            "file": csv_file
        }
        
        # Note: We use format='multipart' for file uploads
        response = self.client.post(self.data_url, data, format='multipart', HTTP_X_API_KEY=self.raw_key)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TelemetryLog.objects.filter(device=self.device).count(), 2)
        print("✅ CSV Batch Ingestion: Passed.")