import logging
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Device, User
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
from .tokens import email_verification_token
from django.contrib.auth import get_user_model
from .utils import send_verification_email # The function we built in the previous step

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
    

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save() # is_active is False by default
        
        # 1. Generate Token and UID
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        
        # 2. Build the Verification URL (Points to your React Frontend)
        verify_url = f"http://localhost:5173/verify-email/{uid}/{token}/"
        
        # 3. Send the Email
        send_mail(
            subject="Verify your IIoT Bridge Account",
            message=f"Hi {user.username}, welcome to the platform. Verify here: {verify_url}",
            from_email="noreply@iotbridge.com",
            recipient_list=[user.email],
            fail_silently=False,
        )


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
        

# class RegisterView(generics.CreateAPIView):
#     """
#     Public Endpoint for New User Registration:
#     - Logic: Validates input -> Hashes Password -> Creates User
#     - Security: AllowAny (No token required)
#     """
#     queryset = User.objects.all()
#     permission_classes = (permissions.AllowAny,)
#     serializer_class = RegisterSerializer

#     # throttling burst limit 
#     throttle_classes = [ScopedRateThrottle]
#     throttle_scope = 'burst'

#     def post(self, request, *args, **kwargs):
#         response = super().post(request, *args, **kwargs)
#         # Custom log for security monitoring
#         logger.info(f"New user account created: {request.data.get('username')}")
#         return response