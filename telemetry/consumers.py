# telemetry/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TelemetryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.subscribed_groups = set()
        await self.accept()

    async def disconnect(self, close_code):
        # Cleanup all subscriptions on disconnect
        for group_name in self.subscribed_groups:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive(self, text_data):
        """Handles explicit subscribe/unsubscribe requests from React."""
        try:
            payload = json.loads(text_data)
            action = payload.get('action')
            device_id = payload.get('device_id')
            
            if not device_id:
                return

            group_name = f"device_{device_id}"

            if action == 'subscribe':
                await self.channel_layer.group_add(group_name, self.channel_name)
                self.subscribed_groups.add(group_name)
                await self.send(json.dumps({"status": "subscribed", "device": device_id}))
                
            elif action == 'unsubscribe':
                await self.channel_layer.group_discard(group_name, self.channel_name)
                self.subscribed_groups.discard(group_name)
                await self.send(json.dumps({"status": "unsubscribed", "device": device_id}))
                
        except json.JSONDecodeError:
            await self.send(json.dumps({"error": "Invalid JSON"}))

    async def live_telemetry(self, event):
        """
        Pushes the broadcasted event to the WebSocket.
        Triggered by channel_layer.group_send in the Ingestion Worker.
        """
        # We send highly compressed JSON to minimize network bandwidth
        await self.send(text_data=json.dumps({
            "live_data": event["payload"] # The telemetry data array
        }))
    
    async def command_acknowledgment(self, event):
        """
        Pushes command acknowledgment updates to the WebSocket.
        Triggered when hardware acknowledges command execution.
        """
        await self.send(text_data=json.dumps({
            "type": "command_ack",
            "command_id": event["command_id"],
            "status": event["status"],
            "device_id": event["device_id"],
            "timestamp": event["timestamp"]
        }))