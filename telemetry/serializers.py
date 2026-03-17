"""
This file acts as a validator, ensuring that if a device sends "text" where it should be a "number," the system rejects it before it hits the database.
"""

from rest_framework import serializers
from .models import TelemetryLog, MediaLog, AlertThreshold
from devices.models import Device

class TelemetryIngestSerializer(serializers.ModelSerializer):
    device_id = serializers.UUIDField()

    class Meta:
        model = TelemetryLog
        fields = ['device_id', 'label', 'value', 'timestamp']

    def validate_value(self, value):
        # Enforce the documented industrial sanity checks [-1000 to 5000]
        if not (-1000 <= value <= 5000):
            raise serializers.ValidationError("Value out of hardware sanity bounds.")
        return value

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