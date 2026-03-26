# devices/api/ack.py
from rest_framework.views import APIView
from rest_framework.response import Response
from devices.models import CommandQueue, CommandState
from channels.layers import get_channel_layer
from django.utils import timezone
import json

class CommandAcknowledgementView(APIView):
    def post(self, request, device_id):
        cmd_id = request.data.get('cmd_id')
        outcome = request.data.get('outcome') # 'SUCCESS' or 'FAILED'
        
        try:
            command = CommandQueue.objects.get(id=cmd_id, device_id=device_id)
        except CommandQueue.DoesNotExist:
            return Response({"error": "Command not found"}, status=404)

        # Update command status
        if outcome == 'SUCCESS':
            command.status = CommandState.EXECUTED
        else:
            command.status = CommandState.FAILED
            
        command.save(update_fields=['status', 'updated_at'])
        
        # Send WebSocket notification to UI
        channel_layer = get_channel_layer()
        group_name = f"device_{device_id}"
        
        try:
            channel_layer.group_send(
                group_name,
                {
                    'type': 'command_acknowledgment',
                    'command_id': cmd_id,
                    'status': command.status,
                    'device_id': device_id,
                    'timestamp': timezone.now().isoformat()
                }
            )
        except Exception as e:
            # WebSocket notification failed, but command was updated
            print(f"WebSocket notification failed: {e}")
        
        return Response({"status": "Acknowledged", "command_status": command.status})