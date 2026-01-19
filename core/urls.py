"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from telemetry.views import *
from devices.views import  ActivateAccountView
from devices.views import *
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.http import JsonResponse

#0.0 Defining the Health Check view directly here
def api_root(request):
    return JsonResponse({
        "system": "EastCoast Bridge",
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "access": "Restricted (Titanium Clearance)"
    })

# 0.1 creating mini access to check for issue with superadmin
from django.http import HttpResponse
from django.contrib.auth import get_user_model
import os

def emergency_admin_setup(request):
    User = get_user_model()
    
    # 1. HARDCODE the credentials here
    TARGET_USERNAME = "eastcoast"
    TEMP_PASSWORD = "eastcoast_password"  # <--- We will use this EXACT string
    
    try:
        # Get or Create the user
        user, created = User.objects.get_or_create(username=TARGET_USERNAME)
        
        # 2. FORCE the password and permissions
        user.set_password(TEMP_PASSWORD)
        user.email = "admin@eastcoast.com"
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True  # crucial!
        user.save()
        
        action = "Created" if created else "Updated"
        
        return HttpResponse(f"""
            <h1>✅ Emergency Override Complete</h1>
            <p>User: <b>{TARGET_USERNAME}</b></p>
            <p>Password: <b>{TEMP_PASSWORD}</b></p>
            <p>Status: {action}, Active, Staff, Superuser</p>
            <br>
            <a href='/admin/login/?next=/admin/'>👉 Click here to Log In</a>
        """)
    except Exception as e:
        return HttpResponse(f"❌ Error: {e}")
    


# 1. Setting for Router for Management APIs
router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')

urlpatterns = [
    path('emergency-setup/', emergency_admin_setup),
    path('admin/', admin.site.urls),
    path('', api_root, name='api_root'),

    # --- AUTHENTICATION ---
    # Sign up
    path('api/v1/auth/register/', RegisterView.as_view(), name='register'),

    path('register/', RegisterView.as_view(), name='register'),
    path('api/v1/auth/activate/<str:uidb64>/<str:token>/', ActivateAccountView.as_view(), name='activate-account'),
    path('api/v1/auth/resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path ('api/v1/auth/password-reset/', RequestPasswordResetView.as_view(), name='password-reset'),
    path('api/v1/auth/password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),

    # Login: Returns Access + Refresh tokens
    path('api/v1/auth/login/', TokenObtainPairView.as_view(), name='login'),
    # Refresh: Returns a new Access token using the Refresh token
    path('api/v1/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Logout: Blacklists the Refresh token
    path('api/v1/auth/logout/', LogoutView.as_view(), name='logout'),

    # --- DEVICE MANAGEMENT (User Dashboard) ---
    path('api/v1/', include(router.urls)),

    # --- DATA INGESTION (IoT Hardware) ---
    path('api/v1/ingest/', DataIngestionView.as_view(), name='data-ingest'), # The 'Front Door' for all the IoT Hardware
    path('api/v1/ingest/media/', MediaIngestionView.as_view(), name='media-ingest'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
