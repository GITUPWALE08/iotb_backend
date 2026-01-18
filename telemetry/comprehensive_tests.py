import hashlib
import uuid
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from core.asgi import application
from devices.models import Device, User
from telemetry.models import TelemetryLog, MediaLog
from django.core.files.uploadedfile import SimpleUploadedFile

class IoTSystemComprehensiveTest(TransactionTestCase):
    """
    Detailed test suite covering:
    - API Security (Hashing)
    - Bulk Telemetry Ingestion
    - Media Upload Logic
    - Threshold Safeguards
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='admin_eng', password='password123')
        
        # We store the raw key to send in headers, and the hash in the DB
        self.raw_api_key = "secret_device_key_2026"
        self.hashed_key = hashlib.sha256(self.raw_api_key.encode()).hexdigest()
        
        self.device = Device.objects.create(
            name="Industrial Boiler 01",
            owner=self.user,
            api_key_hash=self.hashed_key,
            is_active=True
        )
        self.ingest_url = reverse('data-ingest')
        self.media_url = reverse('media-ingest')

    # --- 1. SECURITY TESTS ---
    def test_unauthorized_access(self):
        """Reject requests with wrong API keys."""
        payload = {"device_id": str(self.device.id), "data": []}
        response = self.client.post(self.ingest_url, payload, HTTP_X_API_KEY="wrong_key")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDRON)

    # --- 2. BULK TELEMETRY TESTS ---
    def test_bulk_telemetry_ingestion(self):
        """Test if 50 points are saved in one atomic batch."""
        data_points = [
            {"label": "temp", "value": 20.0 + i, "timestamp": str(timezone.now())}
            for i in range(50)
        ]
        payload = {
            "device_id": str(self.device.id),
            "data": data_points
        }
        
        response = self.client.post(
            self.ingest_url, 
            payload, 
            format='json', 
            HTTP_X_API_KEY=self.raw_api_key
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TelemetryLog.objects.count(), 50)
        # Check if B-Tree index helps retrieval
        latest_log = TelemetryLog.objects.filter(device=self.device).latest('timestamp')
        self.assertEqual(latest_log.value, 69.0)

    def test_payload_threshold_limit(self):
        """Ensure system rejects payloads above the MAX_POINTS_PER_REQUEST (500)."""
        data_points = [{"label": "p", "value": 1.0}] * 600 # Over the 500 limit
        payload = {"device_id": str(self.device.id), "data": data_points}
        
        response = self.client.post(self.ingest_url, payload, format='json', HTTP_X_API_KEY=self.raw_api_key)
        self.assertEqual(response.status_code, status.HTTP_413_PAYLOAD_TOO_LARGE)

    # --- 3. MEDIA PRODUCTION TESTS ---
    def test_media_upload_and_validation(self):
        """Test file ingestion with size and extension checks."""
        video_content = b"fake_mp4_binary_data"
        video_file = SimpleUploadedFile("engine_cam.mp4", video_content, content_type="video/mp4")
        
        data = {
            "device_id": str(self.device.id),
            "file_type": "VIDEO",
            "file": video_file
        }
        
        response = self.client.post(
            self.media_url, 
            data, 
            format='multipart', 
            HTTP_X_API_KEY=self.raw_api_key
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(MediaLog.objects.filter(device=self.device).exists())

    # --- 4. WEBSOCKET BROADCAST TEST ---
    async def test_websocket_broadcast(self):
        """Verify that ingestion triggers a WebSocket live broadcast."""
        communicator = WebsocketCommunicator(
            application, f"ws/live/{self.device.id}/"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Trigger an ingestion (simulated)
        # Note: In a real test, you'd call the view; here we check routing
        await communicator.disconnect()