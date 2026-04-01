from datetime import timezone
import logging
from psycopg2 import IntegrityError
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import CommandState, Device, User, DeviceProperty, CommandQueue
from .serializers import DeviceSerializer, RegisterSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework import generics, permissions
from rest_framework.throttling import ScopedRateThrottle
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from .tokens import email_verification_token
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_str
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .tokens import email_verification_token
from django.contrib.auth import get_user_model
from .utils import send_verification_email
import secrets, hashlib
from django.contrib.auth.tokens import default_token_generator
import json
import paho.mqtt.publish as publish
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from .queue import enqueue_mqtt_command
from .tasks import process_command_delivery


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
        1. Generate a secure random key (e.g., sk_live_...)
        2. Hash it for the database (SHA-256)
        3. Save the Hash to DB, but attach Raw Key to object for the UI
        """
        # Generate the Raw Key (The user sees this ONCE)
        raw_key = f"sk_{secrets.token_urlsafe(24)}"
        
        # Hash it (The database stores this)
        hashed_key = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        
        # 2. Perform the initial save via the serializer (assigns the owner)
        instance = serializer.save(owner=self.request.user)
        
        # 3. Explicitly assign the hash to the model instance. 
        # This bypasses the serializer so `editable=False` doesn't block it.
        instance.api_key_hash = hashed_key
        instance.save(update_fields=['api_key_hash'])
        
        # 4. Attach the raw key so the UI can display it in the response payload
        instance.raw_api_key = raw_key
        
        
        logger.info(f"New Device {instance.id} created with new secure key registered by user: {self.request.user.username}")
        

    def destroy(self, request, *args, **kwargs):
        """
        Custom delete logic: Log the deletion of hardware.
        """
        instance = self.get_object()
        logger.warning(f"Device {instance.id} being deleted by {request.user}")
        return super().destroy(request, *args, **kwargs)
        
    

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
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            # 1. Save the user instance once
            user = serializer.save()
            
            # 2. Force the account to be inactive via direct SQL (prevents double-save mutations)
            User.objects.filter(pk=user.pk).update(is_active=False)
            user.refresh_from_db() # Refresh the Python object to match the database

            # 3. Send the "Onyx & Cyan" verification email
            try:
                send_verification_email(user, request)
            except Exception as e:
                # Log this error in production (Sentry/CloudWatch)
                print(f"Email sending failed: {e}")
                logger.error(f"Email sending failed for {user.email}: {e}")
                # We still return 201 because the user WAS created. 
                # They can use the "Resend Verification" button later.
            
            return Response(
                {"message": "Account initialized. Please check your email to activate protocol."},
                status=status.HTTP_201_CREATED
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# This decorator is CRITICAL. It stops Django from blocking the HTML form POST request.
@method_decorator(csrf_exempt, name='dispatch')
class ActivateAccountView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token):
        print(f"==== [ACTIVATION] GET Request (Shield) Received for UID: {uidb64} ====")
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception as e:
            return self._error_response("Invalid activation link")

        # Check if they are already active
        if user.is_active and user.is_email_verified:
            return self._success_response(user, already_active=True)

        # Check token validity before showing the button
        if not email_verification_token.check_token(user, token):
            return self._error_response(
                "Activation link has expired or is invalid.",
                "Please request a new verification email below."
            )

        # TOKEN IS VALID: Show the Bot-Proof HTML Interceptor Button
        action_url = f"/api/v1/auth/activate/{uidb64}/{token}/"
        interceptor_html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <style>
                    body {{ font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 10vh; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; margin: 0; min-height: 100vh; }}
                    .container {{ max-width: 500px; margin: 0 auto; padding: 40px 20px; background: rgba(255, 255, 255, 0.1); border-radius: 16px; backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); }}
                    .title {{ color: #00D2FF; font-size: 28px; font-weight: 600; margin-bottom: 16px; }}
                    .message {{ color: #8b949e; font-size: 16px; margin-bottom: 32px; line-height: 1.5; }}
                    .verify-btn {{ display: inline-block; background: #00D2FF; color: #000; padding: 12px 24px; border: none; border-radius: 8px; font-weight: 600; font-size: 16px; cursor: pointer; transition: all 0.2s ease; }}
                    .verify-btn:hover {{ background: #00a8e6; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0, 210, 255, 0.3); }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="title">Almost there!</div>
                    <div class="message">Click the button below to securely verify your email address and activate your account.</div>
                    <form method="POST" action="{action_url}">
                        <button type="submit" class="verify-btn">
                            Verify & Activate
                        </button>
                    </form>
                </div>
            </body>
        </html>
        """
        return HttpResponse(interceptor_html)


    def post(self, request, uidb64, token):
        print(f"==== [ACTIVATION] POST Request Received for UID: {uidb64} ====")
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception as e:
            return self._error_response("Invalid user identification.")

        # Prevent double-activation errors if they click the button twice fast
        if user.is_active and user.is_email_verified:
            return self._success_response(user, already_active=True)

        if email_verification_token.check_token(user, token):
            print("==== [ACTIVATION] Token is VALID. Updating user... ====")
            
            try:
                # 1. Update the Python object
                user.is_active = True
                user.is_email_verified = True
                user.save(update_fields=['is_active', 'is_email_verified'])
                
                # 2. Force raw SQL update as backup
                User.objects.filter(pk=uid).update(is_active=True, is_email_verified=True)
                
                print(f"==== [ACTIVATION] SUCCESS: {user.email} is now active ====")
                return self._success_response(user, already_active=False)

            except Exception as db_error:
                print(f"==== [ACTIVATION] DATABASE ERROR: {db_error} ====")
                return self._error_response("Database error during activation.", "Please try again.")
        else:
            print("==== [ACTIVATION] Token INVALID or CONSUMED on POST ====")
            return self._error_response("Activation link expired.", "Please request a new verification email.")

    def _success_response(self, user, already_active=False):
        """Generates your themed success response"""
        title = "Account Already Activated" if already_active else "Account Activated Successfully! 🎉"
        message = f"Welcome back to EastCoast Bridge, {user.username}!" if already_active else f"Welcome to EastCoast Bridge, {user.username}!"
        submessage = "Your account is already active and ready to use." if already_active else "Your account has been activated and is ready to use."
        
        success_html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <style>
                    body {{ font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 10vh; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; margin: 0; min-height: 100vh; }}
                    .container {{ max-width: 500px; margin: 0 auto; padding: 40px 20px; background: rgba(255, 255, 255, 0.1); border-radius: 16px; backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); }}
                    .title {{ color: #10b981; font-size: 28px; font-weight: 600; margin-bottom: 16px; }}
                    .message {{ color: #8b949e; font-size: 16px; margin-bottom: 24px; line-height: 1.5; }}
                    .submessage {{ color: #6b7280; font-size: 14px; margin-bottom: 32px; }}
                    .login-btn {{ display: inline-block; background: #00D2FF; color: #000; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; transition: all 0.2s ease; }}
                    .login-btn:hover {{ background: #00a8e6; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0, 210, 255, 0.3); }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="title">{title}</div>
                    <div class="message">{message}</div>
                    <div class="submessage">{submessage}</div>
                    <a href="{settings.FRONTEND_URL}/login" class="login-btn">Go to Login →</a>
                </div>
            </body>
        </html>
        """
        return HttpResponse(success_html)

    def _error_response(self, message, submessage=""):
        """Generates your themed error response"""
        error_html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <style>
                    body {{ font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 10vh; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white; margin: 0; min-height: 100vh; }}
                    .container {{ max-width: 500px; margin: 0 auto; padding: 40px 20px; background: rgba(255, 255, 255, 0.1); border-radius: 16px; backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); }}
                    .title {{ color: #ef4444; font-size: 28px; font-weight: 600; margin-bottom: 16px; }}
                    .message {{ color: #8b949e; font-size: 16px; margin-bottom: 24px; line-height: 1.5; }}
                    .submessage {{ color: #6b7280; font-size: 14px; margin-bottom: 32px; }}
                    .resend-btn {{ display: inline-block; background: transparent; color: #00D2FF; padding: 12px 24px; text-decoration: none; border: 1px solid #00D2FF; border-radius: 8px; font-weight: 600; font-size: 14px; transition: all 0.2s ease; }}
                    .resend-btn:hover {{ background: #00D2FF; color: #000; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="title">Activation Failed</div>
                    <div class="message">{message}</div>
                    <div class="submessage">{submessage}</div>
                    <a href="{settings.FRONTEND_URL}/resend-verification" class="resend-btn">Request New Verification Email</a>
                </div>
            </body>
        </html>
        """
        return HttpResponse(error_html, status=400)       

# class ActivateAccountView(APIView):
#     """
#     The "Key" to the Fortress:
#     - Decodes the UID from the email link.
#     - Validates the one-time token.
#     - Activates the user account.
#     """
#     permission_classes = [permissions.AllowAny]

#     def post(self, request, uidb64, token):
#         try:
#             # 1. Decode the User ID
#             uid = force_str(urlsafe_base64_decode(uidb64))
#             user = User.objects.get(pk=uid)
#         except (TypeError, ValueError, OverflowError, User.DoesNotExist):
#             user = None

#         # 2. Validate Token
#         if user is not None and email_verification_token.check_token(user, token):
#             user.is_active = True
#             user.is_email_verified = True
#             user.save()
            
#             logger.info(f"Account activated successfully: {user.username}")
#             return Response({"message": "Account activated successfully!"}, status=status.HTTP_200_OK)
#         else:
#             logger.warning(f"Failed activation attempt for UID: {uidb64}")
#             return Response({"error": "Activation link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    # This should be open to unauthenticated users
    permission_classes = [permissions.AllowAny] 

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
    permission_classes = [permissions.AllowAny] # Publicly accessible

    def post(self, request):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            # Point this to your Vercel frontend URL
            reset_link = f"{settings.FRONTEND_URL}/password-reset-confirm/{uid}/{token}/"
            
            try:
                # Send the branded email (similar to verification)
                send_mail(
                    'Reset Your EastCoast Bridge Security String',
                    f'Use this link to reset your password: {reset_link}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                # Log this error in production (Sentry/CloudWatch)
                print(f"Email sending failed: {e}")
                logger.error(f"Email sending failed for {user.email}: {e}")
            
        return Response({"message": "If an account exists, a reset link has been sent."}, status=200)
    

class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]  # Publicly accessible

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
            enqueue_mqtt_command(command.id)
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


@api_view(['POST'])
def cancel_command(request, device_id, command_id):
    """Allows a user to abort a command if it hasn't been executed yet."""
    command = get_object_or_404(CommandQueue, id=command_id, device__id=device_id)
    
    if command.status in ['PENDING', 'QUEUED', 'DELIVERED']:
        command.status = 'CANCELLED'
        command.save()
        return Response({"status": "Command cancelled successfully."})
    
    return Response({"error": f"Too late. Command is already {command.status}."}, status=400)


@api_view(['GET'])
def get_command_queue(request, device_id):
    """
    Used by the React UI to see command queue activity without changing command state.

    Default behavior returns unresolved commands only.
    Pass `include_resolved=true` to include EXECUTED/FAILED/CANCELLED/EXPIRED/etc.
    """
    device = get_object_or_404(Device, id=device_id)

    include_resolved = str(request.query_params.get('include_resolved', 'false')).lower() in [
        '1', 'true', 'yes', 'y'
    ]
    limit = int(request.query_params.get('limit', 50))

    qs = CommandQueue.objects.filter(device=device).order_by('-created_at')
    if not include_resolved:
        # We want to see commands that are either waiting to be sent OR sent but not yet executed.
        qs = qs.filter(status__in=['PENDING', 'QUEUED', 'DELIVERED'])

    active_commands = qs[:limit]

    data = [
        {
            "command_id": cmd.id,
            "identifier": cmd.target_property.identifier,
            "target_value": cmd.target_value,
            "status": cmd.status,
            "created_at": cmd.created_at.isoformat(),
            "updated_at": cmd.updated_at.isoformat(),
        } for cmd in active_commands
    ]

    return Response({"commands": data})


@api_view(['PUT', 'DELETE'])
def device_property_detail(request, device_id, property_id):
    """Handles renaming or deleting a specific device property."""
    prop = get_object_or_404(DeviceProperty, id=property_id, device__id=device_id)

    if request.method == 'DELETE':
        prop.delete()
        return Response({"status": "Property deleted."}, status=204)

    elif request.method == 'PUT':
        # We only allow updating the human-readable name for safety. 
        # Changing the JSON identifier requires deleting and recreating.
        new_name = request.data.get('name')
        if new_name:
            prop.name = new_name
            prop.save()
            return Response({"status": "Property renamed.", "name": prop.name})
        return Response({"error": "Name is required."}, status=400)
       

class SubmitCommandView(APIView):
    def post(self, request):
        device_id = request.data.get('device_id')
        property_id = request.data.get('property_id')
        value = request.data.get('value')
        idempotency_key = request.headers.get('Idempotency-Key')
        ttl_seconds = request.data.get('ttl', 86400)

        # 1. Idempotency Protection
        if idempotency_key:
            existing = CommandQueue.objects.filter(device_id=device_id, idempotency_key=idempotency_key).first()
            if existing:
                return Response({"status": "Already queued", "command_id": existing.id}, status=status.HTTP_200_OK)

        # 2. Persist to DB (PENDING)
        try:
            command = CommandQueue.objects.create(
                device_id=device_id,
                target_property_id=property_id,
                target_value=str(value),
                idempotency_key=idempotency_key,
                expires_at=timezone.now() + timezone.timedelta(seconds=ttl_seconds)
            )
        except IntegrityError:
            return Response({"error": "Duplicate command"}, status=status.HTTP_409_CONFLICT)

        # 3. Push to Redis Command Queue via Celery
        process_command_delivery.delay(command.id)

        # 4. Return immediately
        return Response({
            "status": "Accepted", 
            "command_id": command.id,
            "state": CommandState.PENDING
        }, status=status.HTTP_202_ACCEPTED)