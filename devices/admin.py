from django.contrib import admin
from .models import User, Device, DeviceCommand

admin.site.register(User)
admin.site.register(Device)
admin.site.register(DeviceCommand)