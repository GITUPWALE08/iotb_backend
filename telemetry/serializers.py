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
        fields = [
            'id',
            'device',
            'parameter',
            'operator',
            'min_value',
            'max_value',
            'cooldown_minutes',
            'is_active',
            'last_triggered',
            'notification_channel',
            'notification_target',
        ]
        read_only_fields = ['id', 'device', 'last_triggered']

    def create(self, validated_data):
        # We need to manually inject the 'device' from the URL
        device_id = self.context['view'].kwargs['device_id']
        device = Device.objects.get(id=device_id)
        return AlertThreshold.objects.create(device=device, **validated_data)

    def validate(self, attrs):
        channel = attrs.get('notification_channel', 'EMAIL')
        target = attrs.get('notification_target') or ''

        if not target.strip():
            raise serializers.ValidationError({
                "notification_target": "This field is required for the selected notification channel."
            })

        if channel == 'EMAIL' and '@' not in target:
            raise serializers.ValidationError({
                "notification_target": "Please enter a valid email address."
            })

        # For SMS we only ensure it's non-empty; actual formatting can be enforced later.
        return attrs