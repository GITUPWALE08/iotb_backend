# devices/api/polling.py
from datetime import timezone

from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from devices.models import CommandQueue, CommandState

class DevicePollCommandsView(APIView):
    """Used by individual HTTPS devices to pull pending commands."""
    
    @transaction.atomic
    def get(self, request, device_id):
        # Transaction lock prevents duplicate polling race conditions
        commands = CommandQueue.objects.select_for_update(skip_locked=True).filter(
            device_id=device_id,
            status=CommandState.QUEUED,
            expires_at__gt=timezone.now()
        )[:50] # Batch limit

        if not commands:
            return Response([])

        response_data = []
        commands_to_update = []

        for cmd in commands:
            response_data.append({
                "cmd_id": cmd.id,
                "property": cmd.target_property.identifier,
                "value": cmd.target_value
            })
            cmd.status = CommandState.DELIVERED
            commands_to_update.append(cmd)

        # Bulk update to DELIVERED
        CommandQueue.objects.bulk_update(commands_to_update, ['status', 'updated_at'])

        return Response(response_data)

class GatewayPollCommandsView(APIView):
    """Used by Gateways to pull commands for ALL their child devices in one batch."""
    
    @transaction.atomic
    def get(self, request, gateway_id):
        # Fetch commands where the device's assigned gateway matches
        commands = CommandQueue.objects.select_for_update(skip_locked=True).filter(
            device__gateway_id=gateway_id,
            status=CommandState.QUEUED,
            expires_at__gt=timezone.now()
        )[:200]

        response_data = []
        for cmd in commands:
            response_data.append({
                "device_id": str(cmd.device_id),
                "cmd_id": cmd.id,
                "property": cmd.target_property.identifier,
                "value": cmd.target_value
            })
            cmd.status = CommandState.DELIVERED

        CommandQueue.objects.bulk_update(commands, ['status', 'updated_at'])
        return Response(response_data)