from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # This matches: ws://127.0.0.1:8000/ws/live/<device_id>/
    re_path(r'ws/live/(?P<device_id>[^/]+)/$', consumers.TelemetryConsumer),
]