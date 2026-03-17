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

import socket
from django.core.mail import send_mail
from django.http import HttpResponse
from django.conf import settings
import os
from telemetry.views import AlertViewSet

def debug_email(request):
    try:
        # 1. Resolve Gmail's IP (Tests DNS/Network)
        try:
            gmail_ip = socket.gethostbyname('smtp.gmail.com')
        except Exception as e:
            gmail_ip = f"DNS FAILED: {e}"

        # 2. Capture Settings
        port = getattr(settings, 'EMAIL_PORT', 'Unknown')
        use_ssl = getattr(settings, 'EMAIL_USE_SSL', 'Unknown')
        use_tls = getattr(settings, 'EMAIL_USE_TLS', 'Unknown')
        backend = settings.EMAIL_BACKEND
        
        info = (
            f"Target: smtp.gmail.com ({gmail_ip}) <br>"
            f"Port: <b>{port}</b> <br>"
            f"SSL: {use_ssl} | TLS: {use_tls} <br>"
            f"Backend: {backend} <hr>"
        )
        
        # 3. Attempt Send
        send_mail(
            'Render Port Test',
            'Testing connectivity.',
            settings.EMAIL_HOST_USER,
            [settings.EMAIL_HOST_USER],
            fail_silently=False,
        )
        return HttpResponse(info + "<h1 style='color:green'>✅ Sent!</h1>")
    except Exception as e:
        return HttpResponse(info + f"<h1 style='color:red'>❌ Failed: {e}</h1>")


# 1. Setting for Router for Management APIs
router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')

urlpatterns = [
    # path('emergency-setup/', emergency_admin_setup),
    path('debug-email/', debug_email), 
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
    

    # ✅ NEW: Alerting Routes
    path('api/v1/devices/<str:device_id>/alerts/', AlertViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('api/v1/devices/<str:device_id>/commands/<int:command_id>/cancel/', cancel_command, name='cancel-command'),
    path('api/v1/alerts/<int:pk>/', AlertViewSet.as_view({'delete': 'destroy'})),
    # Dashboard UI endpoint to view the queue safely
    path('api/v1/devices/<str:device_id>/queue/', get_command_queue, name='command-queue'),
    # Update/Delete a specific property
    path('api/v1/devices/<str:device_id>/properties/<int:property_id>/', device_property_detail, name='property-detail'),

      # 1. Properties (GET/POST)
    path('api/v1/devices/<str:device_id>/properties/', device_properties, name='device-properties'),
    
    # 2. Dispatch a command from the UI (POST)
    path('api/v1/devices/<str:device_id>/dispatch/', dispatch_command, name='dispatch-command'),
    
    # 3. Device polling for commands (GET)
    path('api/v1/devices/<str:device_id>/poll/', poll_pending_commands, name='poll-commands'),

    path('api/v1/telemetry/device/<str:device_id>/ohlc/', telemetry_chart_endpoint, name='telemetry-ohlc'),

    # --- DATA INGESTION (IoT Hardware) ---
    path('api/v1/ingest/', DataIngestionView.as_view(), name='data-ingest'), # The 'Front Door' for all the IoT Hardware
    path('api/v1/ingest/media/', MediaIngestionView.as_view(), name='media-ingest'),

    # ---dashboard analytics & visualization---
    path('api/v1/devices/<str:device_id>/history/', device_history, name='device-history'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


