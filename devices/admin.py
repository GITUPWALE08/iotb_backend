from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(Device)
admin.site.register(CommandQueue)
admin.site.register(DeviceProperty)