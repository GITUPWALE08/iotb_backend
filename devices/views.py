import logging
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Device, User, DeviceProperty, CommandQueue
from .serializers import DeviceSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework import generics, permissions
from .serializers import RegisterSerializer
from rest_framework.throttling import ScopedRateThrottle
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from .tokens import email_verification_token
from django.core.mail import send_mail
from django.utils.encoding import force_str
from django.conf import settings
from .tokens import email_verification_token
from django.contrib.auth import get_user_model
from .utils import send_verification_email
import secrets, hashlib
from django.contrib.auth.tokens import default_token_generator
import json
import paho.mqtt.publish as publish
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view


User = get_user_model()


logger = logging.getLogger(__name__)

class DeviceViewSet(viewsets.ModelViewSet):
    """
    Production CRUD for IoT Devices:
    - GET /api/v1/devices/          -> List user's devices
    - POST /api/v1/devices/         -> Register new device
    - GET /api/v1/devices/{id}/     -> Detail view
    - PATCH /api/v1/devices/{id}/    -> Rename/Toggle active
    """
    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        CRITICAL SECURITY: This ensures a user ONLY sees their own 
        devices. Even an admin user (unless specified) is restricted here.
        """
        return Device.objects.filter(owner=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        """
        Auto-assign the logged-in user as the owner.
        """
        serializer.save(owner=self.request.user)
        logger.info(f"New device registered by user: {self.request.user.username}")

    def destroy(self, request, *args, **kwargs):
        """
        Custom delete logic: Log the deletion of hardware.
        """
        instance = self.get_object()
        logger.warning(f"Device {instance.id} being deleted by {request.user}")
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        """
        1. Generate a secure random key (e.g., sk_live_...)
        2. Hash it for the database (SHA-256)
        3. Save the Hash to DB, but attach Raw Key to object for the UI
        """
        # Generate the Raw Key (The user sees this ONCE)
        raw_key = f"sk_{secrets.token_urlsafe(24)}"
        
        # Hash it (The database stores this)
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Save to DB with the owner and the HASH
        instance = serializer.save(owner=self.request.user, api_key_hash=hashed_key)
        
        # Attach raw key to the instance so Serializer can show it in the response
        instance.raw_api_key = raw_key
        
        logger.info(f"Device {instance.id} created with new secure key.")
    

class LogoutView(APIView):
    """
    Production-ready Logout:
    - Requires a valid Refresh Token.
    - Adds the token to the server-side Blacklist.
    - Prevents further session hijacking.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            # This puts the token in the 'BlacklistedToken' table in MySQL
            token.blacklist()

            return Response({"message": "Successfully logged out."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Invalid token or already logged out."}, status=status.HTTP_400_BAD_REQUEST)
    

class RegisterView(APIView):
    # Allow anyone to register (no login required)
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            # 1. Save the user instance but don't commit to DB yet if you need custom logic
            # However, standard save() is fine if we update is_active immediately after.
            user = serializer.save()
            
            # 2. Force the account to be inactive
            user.is_active = False
            user.save()
            
            # 3. Send the "Onyx & Cyan" verification email
            try:
                send_verification_email(user, request)
            except Exception as e:
                # Log this error in production (Sentry/CloudWatch)
                print(f"Email sending failed: {e}")
                # We still return 201 because the user WAS created. 
                # They can use the "Resend Verification" button later.
            
            return Response(
                {"message": "Account initialized. Please check your email to activate protocol."},
                status=status.HTTP_201_CREATED
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ActivateAccountView(APIView):
    """
    The "Key" to the Fortress:
    - Decodes the UID from the email link.
    - Validates the one-time token.
    - Activates the user account.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token):
        try:
            # 1. Decode the User ID
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        # 2. Validate Token
        if user is not None and email_verification_token.check_token(user, token):
            user.is_active = True
            user.is_email_verified = True
            user.save()
            
            logger.info(f"Account activated successfully: {user.username}")
            return Response({"message": "Account activated successfully!"}, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Failed activation attempt for UID: {uidb64}")
            return Response({"error": "Activation link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        
        from django.contrib.auth import get_user_model


class ResendVerificationView(APIView):
    # This should be open to unauthenticated users
    permission_classes = [] 

    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                send_verification_email(user, request)
                return Response({"message": "Verification protocol re-initialized."}, status=status.HTTP_200_OK)
            return Response({"error": "Account is already active."}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            # We return 200 even if user doesn't exist for security (preventing email harvesting)
            return Response({"message": "Verification protocol re-initialized."}, status=status.HTTP_200_OK)
        

class RequestPasswordResetView(APIView):
    permission_classes = [] # Publicly accessible

    def post(self, request):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            # Point this to your Vercel frontend URL
            reset_link = f"{settings.FRONTEND_URL}/password-reset-confirm/{uid}/{token}/"
            
            # Send the branded email (similar to verification)
            send_mail(
                'Reset Your EastCoast Bridge Security String',
                f'Use this link to reset your password: {reset_link}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
        return Response({"message": "If an account exists, a reset link has been sent."}, status=200)
    

class PasswordResetConfirmView(APIView):
    permission_classes = []  # Publicly accessible

    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not all([uidb64, token, new_password]):
            return Response({"error": "Incomplete reset data."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Decode the user ID
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid user identification."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Validate the token
        if default_token_generator.check_token(user, token):
            # 3. Securely set the new password
            user.set_password(new_password)
            user.save()
            return Response({"message": "Security String successfully rotated."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid or expired reset token."}, status=status.HTTP_400_BAD_REQUEST)
        

# --- 1. PROPERTY MANAGEMENT (Used by React to define the Digital Twin) ---
@api_view(['GET', 'POST'])
def device_properties(request, device_id):
    device = get_object_or_404(Device, id=device_id)

    if request.method == 'GET':
        properties = DeviceProperty.objects.filter(device=device)
        data = [
            {
                "id": prop.id,
                "name": prop.name,
                "identifier": prop.identifier,
                "property_type": prop.property_type,
                "data_type": prop.data_type,
                "unit": prop.unit,
                "min_value": prop.min_value,
                "max_value": prop.max_value
            } for prop in properties
        ]
        return Response(data)

    elif request.method == 'POST':
        # Create a new property from the React Configuration Tab
        prop = DeviceProperty.objects.create(
            device=device,
            name=request.data.get('name'),
            identifier=request.data.get('identifier'),
            property_type=request.data.get('property_type'),
            data_type=request.data.get('data_type'),
            unit=request.data.get('unit', ''),
            min_value=request.data.get('min_value'),
            max_value=request.data.get('max_value')
        )
        return Response({"status": "Property created", "id": prop.id}, status=201)


# --- 2. COMMAND DISPATCHER (Used by React to send commands) ---
@api_view(['POST'])
def dispatch_command(request, device_id):
    device = get_object_or_404(Device, id=device_id)
    identifier = request.data.get('identifier') # e.g., 'fan_speed'
    target_value = request.data.get('target_value') # e.g., 75

    try:
        target_property = DeviceProperty.objects.get(device=device, identifier=identifier)
    except DeviceProperty.DoesNotExist:
        return Response({"error": "Property not found"}, status=404)

    # 1. Save it to the Mailbox (Command Queue)
    command = CommandQueue.objects.create(
        device=device,
        target_property=target_property,
        target_value=str(target_value),
        status='PENDING'
    )

    # 2. Protocol Routing: If it's MQTT, push it immediately!
    if getattr(device, 'connection_type', 'HTTPS') == 'MQTT':
        topic = f"iot/commands/{device.id}"
        message = json.dumps({
            "identifier": identifier,
            "target_value": target_value,
            "command_id": command.id # The device needs this to acknowledge it later
        })
        try:
            publish.single(topic, payload=message, hostname="localhost", port=1883)
            # We can mark it DELIVERED (but not EXECUTED yet)
            command.status = 'DELIVERED' 
            command.save()
        except Exception as e:
            print(f"MQTT Publish Failed: {e}")

    # If it's HTTPS/Gateway, it just stays 'PENDING' until the device polls for it.
    return Response({"status": "Command queued", "command_id": command.id})


# --- 3. COMMAND POLLING (Used by HTTPS/Gateway physical devices) ---
@api_view(['GET'])
def poll_pending_commands(request, device_id):
    device = get_object_or_404(Device, id=device_id)

    # Get all unread mail
    pending_commands = CommandQueue.objects.filter(device=device, status='PENDING')

    data = [
        {
            "command_id": cmd.id,
            "identifier": cmd.target_property.identifier,
            "target_value": cmd.target_value
        } for cmd in pending_commands
    ]

    # Once the device reads them, mark them as DELIVERED so they aren't fetched twice
    pending_commands.update(status='DELIVERED')

    return Response({"commands": data})

