# devices/api/ack.py
from rest_framework.views import APIView
from rest_framework.response import Response
from devices.models import CommandQueue, CommandState

class CommandAcknowledgementView(APIView):
    def post(self, request, device_id):
        cmd_id = request.data.get('cmd_id')
        outcome = request.data.get('outcome') # 'SUCCESS' or 'FAILED'
        
        try:
            command = CommandQueue.objects.get(id=cmd_id, device_id=device_id)
        except CommandQueue.DoesNotExist:
            return Response({"error": "Command not found"}, status=404)

        if outcome == 'SUCCESS':
            command.status = CommandState.EXECUTED
        else:
            command.status = CommandState.FAILED
            
        command.save(update_fields=['status', 'updated_at'])
        
        return Response({"status": "Acknowledged"})