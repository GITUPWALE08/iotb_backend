import hashlib
import json
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
from .serializers import MediaIngestionSerializer, AlertThresholdSerializer
from devices.models import Device
from rest_framework.throttling import ScopedRateThrottle
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.decorators import api_view,permission_classes
from .queue import push_to_queue
from django.core.cache import cache
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_datetime
from .models import (
    TelemetryLog, 
    TelemetryRollup1Min, 
    TelemetryRollup5Min, 
    TelemetryRollup1Hour, 
    TelemetryRollup1Day,
    AlertThreshold
)
from .indicator_rollup_model import get_indicator_model, get_rollup_model
from telemetry.api.routing import get_rollup_strategy
from telemetry.api.queries import execute_chart_query
from telemetry.utils.cache import get_or_set_chart_cache

from django.db import models




# Professional Logging
logger = logging.getLogger(__name__)

class DataIngestionView(APIView):
    authentication_classes = [] 
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ingestion'

    def post(self, request):
        payload = request.data
        device_id = payload.get("device_id")
        api_key = payload.get("api_key") or request.headers.get("X-API-KEY")
        logger.info(f"Device ID: {device_id} (type: {type(device_id)})")

        if not device_id or not api_key:
            return Response({"error": "Missing device_id or api_key"}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"API Key: '{api_key}' (len: {len(api_key)}")

        # 1. Fast API Key Hash Authentication
        key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        
        logger.info(f"Validation hash: {key_hash}")

        # Optimize lookup by checking existence only
        device_exists = Device.objects.filter(
            id=device_id,
            api_key_hash=key_hash, 
            is_active=True
        ).exists()

        loger.info(f"Query filter: id={device_id}, hash={key_hash}, active=True")

        if not device_exists:
            return Response({"error": "Invalid credentials or inactive device wale"}, status=status.HTTP_401_UNAUTHORIZED)

        # 2. Payload Format Determination
        payload_type = "single"
        if "data" in payload and "base_time" in payload:
            payload_type = "gateway"
        elif "data" in payload:
            payload_type = "bulk"

        # 3. Queue Push (Decoupled execution)
        queue_payload = {
            "type": payload_type,
            "device_id": device_id,
            "raw_payload": payload
        }
        push_to_queue(queue_payload)

        # 4. Immediate Acknowledgement
        return Response({"status": "ACK", "message": "Payload queued for processing"}, status=status.HTTP_202_ACCEPTED)        
    

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


class MultiDeviceChartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST is used to accommodate large lists of device_ids and property_ids.
        Payload: { "devices": ["id1", "id2"], "properties": ["p1"], "start": "...", "end": "..." }
        """
        device_ids = [str(d) for d in request.data.get('devices', [])]
        property_ids = [str(p) for p in request.data.get('properties', [])]
        start_time = parse_datetime(request.data.get('start'))
        end_time = parse_datetime(request.data.get('end'))

        if not all([device_ids, property_ids, start_time, end_time]):
            return Response({"error": "Missing parameters"}, status=400)

        # 1. Routing Strategy
        model, resolution, ttl = get_rollup_strategy(start_time, end_time)

        # 2. Query & Caching
        def fetch_data():
            return execute_chart_query(model, resolution, device_ids, property_ids, start_time, end_time)

        chart_data = get_or_set_chart_cache(
            device_ids, property_ids, start_time, end_time, resolution, ttl, fetch_data
        )

        # 3. Find latest timestamp across all datasets for WS synchronization
        latest_ts = 0
        for devs in chart_data.values():
            for props in devs.values():
                if props.get("timestamps"):
                    latest_ts = max(latest_ts, props["timestamps"][-1])

        # 4. Construct Response with WS Metadata
        return Response({
            "metadata": {
                "resolution": resolution,
                "latest_timestamp": latest_ts,
                "ws_channels": [f"device_{d_id}" for d_id in device_ids],
                "point_limit_applied": resolution == 'raw'
            },
            "data": chart_data
        })


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



def get_safe_chart_data(model_class, device_id, label, start_time, end_time):
    """Safely retrieves OHLCV data enforcing the 50,000 point UI constraint."""
    # Note: If routing to the raw TelemetryLog, 'bucket' should be 'timestamp'
    time_field = 'timestamp' if model_class == TelemetryLog else 'bucket'
    
    queryset = model_class.objects.filter(
        device_id=device_id,
        label=label,
        **{f"{time_field}__gte": start_time},
        **{f"{time_field}__lte": end_time}
    ).order_by(time_field)
    
    # If it's a rollup table, fetch the pre-calculated OHLCV values
    if model_class != TelemetryLog:
        return list(queryset.values('bucket', 'open', 'high', 'low', 'close', 'volume')[:50000])
    
    # If it's the raw table, just fetch timestamp and value
    return list(queryset.values('timestamp', 'value')[:50000])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def telemetry_chart_endpoint(request, id):
    """
    Replaces the dangerous historical GET endpoint.
    Routes queries to the correct aggregation table based on the time window.
    """
    device_id = id
    identifier = request.GET.get('identifier')
    start_time_str = request.GET.get('start')
    end_time_str = request.GET.get('end')

    if not all([identifier, start_time_str, end_time_str]):
        return Response({"error": "Missing required parameters: identifier, start, end"}, status=400)

    start_time = parse_datetime(start_time_str)
    end_time = parse_datetime(end_time_str)
    time_delta = end_time - start_time
    
    # 1. QUERY ROUTING LOGIC
    if time_delta <= timedelta(hours=12):
        model = TelemetryLog
        res_key = "raw"
    elif time_delta <= timedelta(days=7):
        model = TelemetryRollup1Min
        res_key = "1m"
    elif time_delta <= timedelta(days=90):
        model = TelemetryRollup1Hour
        res_key = "1h"
    else:
        model = TelemetryRollup1Day
        res_key = "1d"

    # 2. REDIS CACHING LOGIC
    cache_key = f"chart:{device_id}:{identifier}:{start_time.timestamp()}:{end_time.timestamp()}:{res_key}"
    cached_payload = cache.get(cache_key)
    
    if cached_payload:
        data = json.loads(cached_payload)
    else:
        # Cache miss: Execute the safe DB query callback
        data = get_safe_chart_data(model, device_id, identifier, start_time, end_time)
        # Cache for 60 seconds to prevent DB spam on rapid UI reloads
        cache.set(cache_key, json.dumps(data), timeout=60)

    return Response({
        "resolution": res_key, 
        "data": data
    })


def get_safe_indicator_chart_data(device_id, property_id, start_time, end_time, resolution_key):
    # Determine models based on router logic
    rollup_model = get_rollup_model(resolution_key)
    indicator_model = get_indicator_model(resolution_key)
    
    # Perform an optimized Django ORM JOIN against the JSONB indicator table
    queryset = rollup_model.objects.filter(
        device_id=device_id,
        property_id=property_id,
        bucket__gte=start_time,
        bucket__lte=end_time
    ).annotate(
        # Extract the JSONB dictionary from the related table
        indicators=models.Subquery(
            indicator_model.objects.filter(
                device_id=models.OuterRef('device_id'),
                property_id=models.OuterRef('property_id'),
                bucket=models.OuterRef('bucket')
            ).values('indicators')[:1]
        )
    ).order_by('bucket').values('bucket', 'open', 'high', 'low', 'close', 'volume', 'indicators')[:50000]
    
    return list(queryset)

