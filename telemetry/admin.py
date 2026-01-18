from django.contrib import admin
from .models import TelemetryLog, MediaLog, AlertThreshold

admin.site.register(TelemetryLog)
admin.site.register(MediaLog)
admin.site.register(AlertThreshold)