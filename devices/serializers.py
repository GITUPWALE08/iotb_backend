from rest_framework import serializers
from .models import Device
from django.contrib.auth.hashers import make_password
from .models import User

class DeviceSerializer(serializers.ModelSerializer):
    # Calculated field for frontend convenience
    status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Device
        fields = [
            'id', 'name', 'is_active', 'is_online', 
            'last_seen', 'created_at', 'status'
        ]
        read_only_fields = ['id', 'is_online', 'last_seen', 'created_at']

    def get_status(self, obj):
        if not obj.is_active:
            return "DEACTIVATED"
        return "ONLINE" if obj.is_online else "OFFLINE"


class RegisterSerializer(serializers.ModelSerializer):
    # We add a write-only password field for security
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        # Crucial: Use make_password to hash the password before saving to MySQL
        validated_data['password'] = make_password(validated_data['password'])
        return super(RegisterSerializer, self).create(validated_data)
