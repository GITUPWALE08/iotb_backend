"""
This file acts as a validator, ensuring that if a device sends "text" where it should be a "number," the system rejects it before it hits the database.
"""

from rest_framework import serializers
from .models import TelemetryLog, MediaLog

class TelemetryIngestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryLog
        fields = ['label', 'value', 'timestamp']
        extra_kwargs = {'timestamp': {'required': False}} # Make optional

class MediaIngestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaLog
        fields = ['file_type', 'file', 'timestamp']
        read_only_fields = ['id']