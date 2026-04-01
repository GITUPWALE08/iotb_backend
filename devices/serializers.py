from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, Device
import logging
import secrets
import hashlib

logger = logging.getLogger(__name__)
# class DeviceSerializer(serializers.ModelSerializer):
#     # Calculated field for frontend convenience
#     status = serializers.SerializerMethodField(read_only=True)

#     class Meta:
#         model = Device
#         fields = [
#             'id', 'name', 'is_active', 'is_online', 
#             'last_seen', 'created_at', 'status'
#         ]
#         read_only_fields = ['id', 'is_online', 'last_seen', 'created_at']

#     def get_status(self, obj):
#         if not obj.is_active:
#             return "DEACTIVATED"
#         return "ONLINE" if obj.is_online else "OFFLINE"


class DeviceSerializer(serializers.ModelSerializer):
    # 1. Status Field (Keep your existing logic)
    status = serializers.SerializerMethodField(read_only=True)
    
    # 2. API Key (read_only = Show it in output, but don't require it in input)
    api_key = serializers.CharField(read_only=True) 

    class Meta:
        model = Device
        fields = [
            'id', 
            'name', 
            'connection_type',  # ✅ Critical for the Frontend Modal to know if it's MQTT/HTTPS
            'is_active', 
            'is_online', 
            'last_seen', 
            'created_at', 
            'status',
            'api_key'           # ✅ The generated key will appear here
        ]
        read_only_fields = ['id', 'is_active', 'is_online', 'last_seen', 'created_at']

    def get_status(self, obj):
        if not obj.is_active:
            return "DEACTIVATED"
        return "ONLINE" if obj.is_online else "OFFLINE"

    def create(self, validated_data):
        """
        Generates the API Key, Hashes it for the DB, 
        and attaches the Raw Key to the response.
        """
        # A. Generate the Raw Key (sk_...)
        raw_key = f"sk_{secrets.token_urlsafe(16)}"
        
        # B. Hash it (SHA-256) for the database
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        validated_data['api_key_hash'] = key_hash
        logger.info(f"Serializer hash: {key_hash}")
        logger.info(f"Serializer raw_key: {raw_key}")
        
        # C. Create the Device
        device = super().create(validated_data)
        
        # D. Attach the Raw Key explicitly so it appears in the JSON response
        device.api_key = raw_key 
        
        return device


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
    

    # def create(self, validated_data):
    #     # This handles the secure password hashing automatically
    #     user = User.objects.create_user(
    #         username=validated_data['username'],
    #         email=validated_data['email'],
    #         password=validated_data['password'],
    #         profession=validated_data.get('profession', '')
    #     )
    #     return user
