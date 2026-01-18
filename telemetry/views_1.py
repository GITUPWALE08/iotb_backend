import hashlib
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import MediaLog
from .serializers import MediaIngestionSerializer
from rest_framework import status
from .models import TelemetryLog
from devices.models import Device
from .serializers import TelemetryIngestionSerializer    
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class ProDataIngestionView(APIView):
    """
    Production-hardened ingestion:
    - Verifies Device
    - Broadcasts to WebSockets for Live Feed
    - Bulk Inserts to MySQL
    """
    authentication_classes = [] 
    permission_classes = []

    # Threshold Constants
    MAX_POINTS_PER_REQUEST = 200  # Threshold to avoid massive bulk inserts

    def post(self, request):
        api_key = request.headers.get('X-API-KEY')
        device_id = request.data.get('device_id')
        payload = request.data.get('data', [])

        if len(payload) > self.MAX_POINTS_PER_REQUEST:
            return Response({
                "error": f"Payload too large. Max {self.MAX_POINTS_PER_REQUEST} points allowed."
            }, status=status.HTTP_413_PAYLOAD_TOO_LARGE)

        if not payload:
            return Response({"error": "Empty payload"}, status=400)

        # 1. Security check
        key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else ""
        device = Device.objects.filter(id=device_id, api_key_hash=key_hash, is_active=True).first()
        
        if not device:
            return Response({"error": "Unauthorized"}, status=403)

        # 2. Live Streaming (WebSockets)
        # We push data to the frontend BEFORE saving to the DB for 0ms latency
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"device_{device_id}", # The unique group for this device
            {
                "type": "live_telemetry",
                "data": payload
            }
        )

        # 3. Bulk Insert (The "Buffering" Logic)
        # In a high-scale prod environment, we'd use Redis here. 
        # For now, we use an atomic bulk_create.
        try:
            with transaction.atomic():
                logs_to_create = [
                    TelemetryLog(
                        device=device,
                        label=d['label'],
                        value=d['value'],
                        timestamp=d.get('timestamp', timezone.now())
                    ) for d in payload if TelemetryIngestionSerializer(data=d).is_valid()
                ]
                
                if logs_to_create:
                    TelemetryLog.objects.bulk_create(logs_to_create)
                    
                    # Update Heartbeat
                    device.last_seen = timezone.now()
                    device.is_online = True
                    device.save(update_fields=['last_seen', 'is_online'])

            return Response({"status": "success", "saved": len(logs_to_create)}, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


class MediaIngestionView(APIView):
    """
    Endpoint for devices to upload Video or Audio files.
    Expects: 
    - X-API-KEY in Headers
    - device_id, file_type, timestamp, and 'file' in Form-Data
    """
    # Use MultiPartParser to handle binary files
    parser_classes = (MultiPartParser, FormParser)
    
    authentication_classes = [] 
    permission_classes = []

    def post(self, request):
        # 1. Extract Credentials
        api_key = request.headers.get('X-API-KEY')
        device_id = request.data.get('device_id')
        
        if not api_key or not device_id:
            return Response({"error": "Missing credentials"}, status=401)

        # 2. Security Check (Same hashing logic as Telemetry)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        try:
            device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
        except Device.DoesNotExist:
            return Response({"error": "Invalid or inactive device"}, status=403)

        # 3. Validate and Save the File
        # We use a serializer to ensure the data format is correct
        serializer = MediaIngestionSerializer(data=request.data)
        
        if serializer.is_valid():
            # Create the MediaLog entry
            # Note: Django handles saving the actual file to MEDIA_ROOT automatically
            serializer.save(device=device)
            
            # Update device last seen
            device.last_seen = serializer.validated_data.get('timestamp')
            device.save(update_fields=['last_seen'])

            return Response({
                "status": "success",
                "message": "Media file uploaded and linked to device",
                "file_path": serializer.data['file']
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


# class DataIngestionView(APIView):
#     """
#     Endpoint for devices to post sensor data.
#     Expects: X-API-KEY in headers and a list of data points.
#     """
#     # Disable global CSRF/Session auth for devices (they use API Keys)
#     authentication_classes = [] 
#     permission_classes = []

#     def post(self, request):
#         api_key = request.headers.get('X-API-KEY')
#         device_id = request.data.get('device_id')
#         payload = request.data.get('data', []) # Should be a list of readings

#         if not api_key or not device_id:
#             return Response({"error": "Missing credentials"}, status=401)

#         # 1. Security Check: Hash the incoming key to compare with DB
#         key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
#         try:
#             device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
#         except Device.DoesNotExist:
#             return Response({"error": "Invalid or inactive device"}, status=403)

#         # 2. Validation & Bulk Processing
#         logs_to_create = []
#         for entry in payload:
#             serializer = TelemetryIngestionSerializer(data=entry)
#             if serializer.is_valid():
#                 # We don't save yet; we add to a list for bulk performance
#                 logs_to_create.append(TelemetryLog(
#                     device=device,
#                     label=serializer.validated_data['label'],
#                     value=serializer.validated_data['value'],
#                     timestamp=serializer.validated_data['timestamp']
#                 ))
        
#         # 3. One single hit to MySQL instead of many
#         if logs_to_create:
#             TelemetryLog.objects.bulk_create(logs_to_create)
            
#             # Update 'last_seen' for the device
#             device.last_seen = logs_to_create[-1].timestamp
#             device.save(update_fields=['last_seen'])

#         return Response({
#             "status": "success", 
#             "received": len(logs_to_create)
#         }, status=status.HTTP_201_CREATED)
