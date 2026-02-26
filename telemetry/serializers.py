"""
This file acts as a validator, ensuring that if a device sends "text" where it should be a "number," the system rejects it before it hits the database.
"""

from rest_framework import serializers
from .models import TelemetryLog, MediaLog, AlertThreshold
from devices.models import Device

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

class AlertThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertThreshold
        fields = ['id', 'parameter', 'operator', 'min_value', 'max_value', 'cooldown_minutes', 'is_active', 'last_triggered']
        read_only_fields = ['id', 'last_triggered']

    def create(self, validated_data):
        # We need to manually inject the 'device' from the URL
        device_id = self.context['view'].kwargs['device_id']
        device = Device.objects.get(id=device_id)
        return AlertThreshold.objects.create(device=device, **validated_data)