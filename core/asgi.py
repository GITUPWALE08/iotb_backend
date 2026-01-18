import os
import django
from django.core.asgi import get_asgi_application

# 1. Set settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# 2. Initialize Django HTTP application FIRST
# This handles the internal app loading sequence correctly
django_asgi_app = get_asgi_application()

# 3. NOW import your routing (after get_asgi_application)
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import telemetry.routing 

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            telemetry.routing.websocket_urlpatterns
        )
    ),
})