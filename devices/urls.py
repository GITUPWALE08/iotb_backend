from django.urls import path
from .views import *

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('activate/<str:uidb64>/<str:token>/', ActivateAccountView.as_view(), name='activate-account'),
    # 1. Properties (GET/POST)
    path('devices/<str:device_id>/properties/', device_properties, name='device-properties'),
    
    # 2. Dispatch a command from the UI (POST)
    path('devices/<str:device_id>/dispatch/', dispatch_command, name='dispatch-command'),
    
    # 3. Device polling for commands (GET)
    path('devices/<str:device_id>/poll/', poll_pending_commands, name='poll-commands'),
]
]

