from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, Device

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
    status = serializers.SerializerMethodField(read_only=True)
    # New field to show the key ONLY when it's first created
    api_key = serializers.CharField(write_only=True, required=False) 

    class Meta:
        model = Device
        fields = [
            'id', 'name', 'is_active', 'is_online', 
            'last_seen', 'created_at', 'status',
            'api_key' # Add this here
        ]
        read_only_fields = ['id', 'is_online', 'last_seen', 'created_at']

    def get_status(self, obj):
        if not obj.is_active:
            return "DEACTIVATED"
        return "ONLINE" if obj.is_online else "OFFLINE"
    
    def to_representation(self, instance):
        """
        Overriding this to inject the raw API Key into the response
        ONLY if it exists on the instance (which we will set in the View).
        """
        representation = super().to_representation(instance)
        if hasattr(instance, 'raw_api_key'):
            representation['api_key'] = instance.raw_api_key
        return representation


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
