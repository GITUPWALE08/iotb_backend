# telemetry/views.py (Cleaned - No Celery)

import hashlib
import json
import logging
from django.db import models
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

# Professional Logging
logger = logging.getLogger(__name__)

# NOTE: All Celery task decorators and imports have been removed
# Rollups are now handled by Django management commands and HTTP endpoints
