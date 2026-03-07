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

from rest_framework import status, viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from .models import TelemetryLog, MediaLog, AlertThreshold
from .serializers import TelemetryIngestionSerializer, MediaIngestionSerializer, AlertThresholdSerializer
from devices.models import Device
from rest_framework.throttling import ScopedRateThrottle
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.decorators import api_view



# Professional Logging
logger = logging.getLogger(__name__)

# class DataIngestionView(APIView):
#     """
#     Industrial-grade Data Ingestion Engine:
#     - Protocol: HTTPS/JSON
#     - Security: SHA-256 Key Hashing
#     - Concurrency: Atomic Bulk Inserts
#     - Live Feed: WebSocket Broadcast
#     - Safeguards: Payload Thresholds & Value Sanitization
#     """
#     authentication_classes = [] 
#     permission_classes = []

#     # --- CONFIGURABLE THRESHOLDS ---
#     MAX_POINTS_PER_REQUEST = 500  # Prevents DB flood
#     VALUE_MIN = -1000.0           # Sanity check for sensor failure
#     VALUE_MAX = 5000.0

#     def post(self, request):
#         # 1. Extraction & Initial Validation
#         api_key = request.headers.get('X-API-KEY')
#         device_id = request.data.get('device_id')

#         # --- NEW: CSV DETECTOR ---
#         csv_file = request.FILES.get('file')
#         if csv_file:
#             if not csv_file.name.endswith('.csv'):
#                 return Response({"error": "File must be a CSV."}, status=400)
            
#             # Read the file into memory
#             decoded_file = csv_file.read().decode('utf-8')
#             io_string = io.StringIO(decoded_file)
#             reader = csv.DictReader(io_string)
#             payload = [row for row in reader]
#         else:
#             payload = request.data.get('data', [])

#             if not isinstance(payload, list):
#                 return Response({"error": "Payload 'data' must be a list."}, status=400)

#             if len(payload) > self.MAX_POINTS_PER_REQUEST:
#                 return Response({
#                     "error": f"Payload too large. Max {self.MAX_POINTS_PER_REQUEST} points per request."
#                 }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

#         # 2. Security: Verify Device Ownership & Status
#         key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else ""
#         try:
#             # B-Tree optimization: Filter by primary ID and hash index
#             device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
#         except (Device.DoesNotExist, ValueError):
#             logger.warning(f"Unauthorized access attempt: Device {device_id}")
#             return Response({"error": "Unauthorized device or invalid API key."}, status=403)

#         # 3. Live Broadcast: Send to WebSockets (Zero-Latency Dashboards)
#         channel_layer = get_channel_layer()
#         async_to_sync(channel_layer.group_send)(
#             f"device_{device_id}",
#             {
#                 "type": "live_telemetry",
#                 "data": payload  # Send raw payload to React for instant update
#             }
#         )

#         # 4. Atomic Processing & Buffering
#         valid_logs = []
#         try:
#             with transaction.atomic():
#                 for entry in payload:
#                     # Sanitize & Validate via Serializer
#                     serializer = TelemetryIngestionSerializer(data=entry)
#                     if serializer.is_valid():
#                         val = serializer.validated_data['value']
                        
#                         # Engineering Sanity Check: Reject impossible physics
#                         if not (self.VALUE_MIN <= val <= self.VALUE_MAX):
#                             continue 

#                         valid_logs.append(TelemetryLog(
#                             device=device,
#                             label=serializer.validated_data['label'],
#                             value=val,
#                             timestamp=serializer.validated_data.get('timestamp', timezone.now())
#                         ))
#                     else:
#                         return Response({"error": "Data format error", "details": serializer.errors}, status=400)

#                 # 5. The B-Tree Win: Bulk Insert
#                 if valid_logs:
#                     TelemetryLog.objects.bulk_create(valid_logs)
                    
#                     # Update Device Heartbeat (Performance: only update specific fields)
#                     device.last_seen = timezone.now()
#                     device.is_online = True
#                     device.save(update_fields=['last_seen', 'is_online'])

#             return Response({
#                 "status": "success", 
#                 "saved_count": len(valid_logs),
#                 "timestamp": timezone.now()
#             }, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             logger.error(f"Database Ingestion Failure: {str(e)}")
#             return Response({"error": "Internal database error."}, status=500)
        
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
        # 1. Extraction & Robust API Key Search
        # Check Body first (Simulators/ESP32), then Headers (Gateways)
        api_key = request.data.get('api_key') or request.headers.get('X-API-KEY')
        device_id = request.data.get('device_id')

        # 2. Payload Normalization (Handle Single Point vs Bulk vs CSV)
        csv_file = request.FILES.get('file')
        if csv_file:
            if not csv_file.name.endswith('.csv'):
                return Response({"error": "File must be a CSV."}, status=400)
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            payload = [row for row in reader]
        else:
            # Check if it's a single point (Simulators/Simple Sensors)
            if 'value' in request.data and 'label' in request.data:
                payload = [request.data] # Wrap it in a list
            else:
                # Check if it's a Bulk Push (Gateways)
                payload = request.data.get('data', [])

        if not isinstance(payload, list):
            return Response({"error": "Invalid payload format. Expected list or single entry."}, status=400)

        # 3. Security: Verify Device Ownership & Status
        key_hash = hashlib.sha256(api_key.encode()).hexdigest() if api_key else ""
        try:
            device = Device.objects.get(id=device_id, api_key_hash=key_hash, is_active=True)
        except (Device.DoesNotExist, ValueError):
            logger.warning(f"Unauthorized access attempt: Device {device_id}")
            return Response({"error": "Unauthorized device or invalid API key."}, status=403)

        # 4. Live Broadcast (Send raw payload to Dashboard)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"device_{device_id}",
            {
                "type": "live_telemetry",
                "data": payload[0] if len(payload) == 1 else payload 
            }
        )

        # 5. Atomic Processing & Buffering
        valid_logs = []
        alerts_triggered = []
        try:
            with transaction.atomic():
                for entry in payload:
                    serializer = TelemetryIngestionSerializer(data=entry)
                    if serializer.is_valid():
                        val = serializer.validated_data['value']
                        lbl = serializer.validated_data['label']
                        
                        # Engineering Sanity Check
                        if not (self.VALUE_MIN <= val <= self.VALUE_MAX):
                            continue 

                        valid_logs.append(TelemetryLog(
                            device=device,
                            label=lbl,
                            value=val,
                            timestamp=serializer.validated_data.get('timestamp', timezone.now())
                        ))

                        self.check_alerts(device, lbl, val, alerts_triggered) # Check for alerts
                    else:
                        # For single points, fail fast. For bulk, you might want to log & skip.
                        if len(payload) == 1:
                            return Response(serializer.errors, status=400)

                if valid_logs:
                    TelemetryLog.objects.bulk_create(valid_logs)
                    
                    # Update Heartbeat
                    device.last_seen = timezone.now()
                    device.is_online = True
                    device.save(update_fields=['last_seen', 'is_online'])

            return Response({
                "status": "ACK", 
                "saved_count": len(valid_logs)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Database Ingestion Failure: {str(e)}")
            return Response({"error": "Internal database error."}, status=500)


    def check_alerts(self, device, label, value, triggered_list):
        """
        Checks if the incoming value violates any AlertThreshold rules.
        """
        # Get active rules for this specific label (e.g., 'temperature')
        rules = AlertThreshold.objects.filter(
            device=device, 
            parameter=label, 
            is_active=True
        )

        for rule in rules:
            is_breach = False
            
            if rule.operator == '>':
                if rule.max_value is not None and value > rule.max_value:
                    is_breach = True
            elif rule.operator == '<':
                if rule.min_value is not None and value < rule.min_value:
                    is_breach = True
            elif rule.operator == '=':
                if rule.min_value is not None and abs(value - rule.min_value) < 0.01:
                    is_breach = True

            if is_breach:
                # Cooldown Check
                now = timezone.now()
                if rule.last_triggered:
                    delta = now - rule.last_triggered
                    if delta.total_seconds() < (rule.cooldown_minutes * 60):
                        continue # Skip (In cooldown)

                # TRIGGER ALERT
                self.send_alert_email(device, rule, value)
                
                # Update Rule State
                rule.last_triggered = now
                rule.save(update_fields=['last_triggered'])
                triggered_list.append(rule.id)

    def send_alert_email(self, device, rule, value):
        subject = f"🚨 ALERT: {device.name} - {rule.parameter.upper()} Critical"
        message = (
            f"Device: {device.name}\n"
            f"Metric: {rule.parameter}\n"
            f"Current Value: {value}\n"
            f"Threshold: {rule.operator} {rule.max_value or rule.min_value}\n\n"
            f"Please check the dashboard immediately."
        )
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [device.owner.email],
                fail_silently=True,
            )
            logger.info(f"Alert email sent to {device.owner.email}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")

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

    throttle_classes = [ScopedRateThrottle]

    throttle_scope = 'ingestion'

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


class AlertViewSet(viewsets.ModelViewSet):
    serializer_class = AlertThresholdSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        If we are listing alerts for a specific device URL: /devices/<id>/alerts/
        """
        device_id = self.kwargs.get('device_id')
        if device_id:
            return AlertThreshold.objects.filter(device_id=device_id, device__owner=self.request.user)
        
        # If we are deleting a specific alert URL: /alerts/<id>/
        return AlertThreshold.objects.filter(device__owner=self.request.user)

    def perform_destroy(self, instance):
        # Optional: Add log logic here before deleting
        instance.delete()



@api_view(['GET'])
def device_history(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    identifier = request.GET.get('identifier') # <--- THE NEW FILTER
    
    # Base query
    logs = TelemetryLog.objects.filter(device=device)
    
    # If the React app asked for a specific sensor, filter it
    if identifier:
        logs = logs.filter(label=identifier)
        
    # Grab the latest 50 logs (or whatever limit you prefer)
    logs = logs.order_by('-timestamp')[:50]
    
    # Format and return...
    data = [
        {"time": log.timestamp, "label": log.label, "value": log.value} 
        for log in reversed(logs) # Reverse so oldest is first for the graph
    ]
    return Response(data)