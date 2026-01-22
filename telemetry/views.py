import hashlib
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import csv
import io
from django.shortcuts import get_object_or_404

from rest_framework import status 
from rest_framework.parsers import MultiPartParser, FormParser
from .models import TelemetryLog, MediaLog
from .serializers import TelemetryIngestionSerializer, MediaIngestionSerializer
from devices.models import Device

# Professional Logging
logger = logging.getLogger(__name__)

class DataIngestionView(APIView):
    """
    Industrial-grade Data Ingestion Engine:
    - Protocol: HTTPS/JSON
    - Security: SHA-256 Key Hashing
    - Concurrency: Atomic Bulk Inserts
    - Live Feed: WebSocket Broadcast
    - Safeguards: Payload Thresholds & Value Sanitization
    """
    authentication_classes = [] 
    permission_classes = []

    # --- CONFIGURABLE THRESHOLDS ---
    MAX_POINTS_PER_REQUEST = 500  # Prevents DB flood
    VALUE_MIN = -1000.0           # Sanity check for sensor failure
    VALUE_MAX = 5000.0

    def post(self, request):
        # 1. Extraction & Initial Validation
        api_key = request.headers.get('X-API-KEY')
        device_id = request.data.get('device_id')

        # --- NEW: CSV DETECTOR ---
        csv_file = request.FILES.get('file')
        if csv_file:
            if not csv_file.name.endswith('.csv'):
                return Response({"error": "File must be a CSV."}, status=400)
            
            # Read the file into memory
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            payload = [row for row in reader]
        else:
            payload = request.data.get('data', [])

            if not isinstance(payload, list):
                return Response({"error": "Payload 'data' must be a list."}, status=400)

            if len(payload) > self.MAX_POINTS_PER_REQUEST:
                return Response({
                    "error": f"Payload too large. Max {self.MAX_POINTS_PER_REQUEST} points per request."
                }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        # 2. Security: Verify Device Ownership & Status
        key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else ""
        try:
            # B-Tree optimization: Filter by primary ID and hash index
            device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
        except (Device.DoesNotExist, ValueError):
            logger.warning(f"Unauthorized access attempt: Device {device_id}")
            return Response({"error": "Unauthorized device or invalid API key."}, status=403)

        # 3. Live Broadcast: Send to WebSockets (Zero-Latency Dashboards)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"device_{device_id}",
            {
                "type": "live_telemetry",
                "data": payload  # Send raw payload to React for instant update
            }
        )

        # 4. Atomic Processing & Buffering
        valid_logs = []
        try:
            with transaction.atomic():
                for entry in payload:
                    # Sanitize & Validate via Serializer
                    serializer = TelemetryIngestionSerializer(data=entry)
                    if serializer.is_valid():
                        val = serializer.validated_data['value']
                        
                        # Engineering Sanity Check: Reject impossible physics
                        if not (self.VALUE_MIN <= val <= self.VALUE_MAX):
                            continue 

                        valid_logs.append(TelemetryLog(
                            device=device,
                            label=serializer.validated_data['label'],
                            value=val,
                            timestamp=serializer.validated_data.get('timestamp', timezone.now())
                        ))
                    else:
                        return Response({"error": "Data format error", "details": serializer.errors}, status=400)

                # 5. The B-Tree Win: Bulk Insert
                if valid_logs:
                    TelemetryLog.objects.bulk_create(valid_logs)
                    
                    # Update Device Heartbeat (Performance: only update specific fields)
                    device.last_seen = timezone.now()
                    device.is_online = True
                    device.save(update_fields=['last_seen', 'is_online'])

            return Response({
                "status": "success", 
                "saved_count": len(valid_logs),
                "timestamp": timezone.now()
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Database Ingestion Failure: {str(e)}")
            return Response({"error": "Internal database error."}, status=500)
        


class MediaIngestionView(APIView):
    """
    Production-hardened Media Gateway:
    - Protocol: Multipart/Form-Data
    - Security: SHA-256 Key Hashing
    - Safeguards: File Size Limits (10MB) & Extension Filtering
    - Reliability: Atomic file-to-db mapping
    """
    parser_classes = (MultiPartParser, FormParser)
    authentication_classes = [] 
    permission_classes = []

    # --- CONFIGURABLE LIMITS ---
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit per file
    ALLOWED_EXTENSIONS = ['.mp4', '.avi', '.wav', '.mp3', '.jpg']

    def post(self, request):
        # 1. Extraction
        api_key = request.headers.get('X-API-KEY')
        device_id = request.data.get('device_id')
        uploaded_file = request.FILES.get('file')

        # 2. Basic Validation
        if not uploaded_file:
            return Response({"error": "No file detected in request."}, status=400)

        # 3. File Size Guard (Critical to prevent Disk Exhaustion)
        if uploaded_file.size > self.MAX_FILE_SIZE:
            return Response({
                "error": f"File too large. Maximum allowed size is {self.MAX_FILE_SIZE / (1024*1024)}MB."
            }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        # 4. Security: Verify Device
        key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else ""
        try:
            device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
        except (Device.DoesNotExist, ValueError):
            logger.warning(f"Unauthorized Media Upload Attempt: Device {device_id}")
            return Response({"error": "Unauthorized device."}, status=403)

        # 5. Extension Validation (Security against Malicious Scripts)
        ext = (uploaded_file.name).lower()[uploaded_file.name.rfind('.'):]
        if ext not in self.ALLOWED_EXTENSIONS:
            return Response({"error": f"Unsupported file extension: {ext}"}, status=400)

        # 6. Atomic Save & Heartbeat
        try:
            with transaction.atomic():
                serializer = MediaIngestionSerializer(data=request.data)
                if serializer.is_valid():
                    # Link device and save file
                    media_instance = serializer.save(device=device)
                    
                    # Update Device Heartbeat
                    device.last_seen = timezone.now()
                    device.save(update_fields=['last_seen'])

                    return Response({
                        "status": "success",
                        "id": media_instance.id,
                        "file_url": serializer.data['file'],
                        "timestamp": timezone.now()
                    }, status=status.HTTP_201_CREATED)
                
                return Response(serializer.errors, status=400)

        except Exception as e:
            logger.error(f"Media Storage Failure: {str(e)}")
            return Response({"error": "Internal server error during file processing."}, status=500) 

    