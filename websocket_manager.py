# connection_manager.py
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.active_public_connections: List[WebSocket] = []  # القناة العامة

        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        channel = f"user_{user_id}"
        async with self.lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = []
            self.active_connections[channel].append(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: str):
        channel = f"user_{user_id}"
        async with self.lock:
            if channel in self.active_connections:
                self.active_connections[channel].remove(websocket)
                if not self.active_connections[channel]:
                    del self.active_connections[channel]

    async def send_personal_notification(self, user_id: str, message: dict):
        channel = f"user_{user_id}"
        print(f"Looking for channel: {channel}")  # Add this
        print(f"Active connections: {self.active_connections}")  # Add this
        async with self.lock:
            if channel in self.active_connections:
                print(f"Found channel {channel} with {len(self.active_connections[channel])} connections")  # Add this
                disconnected = []
                message_str = json.dumps(message)
                for ws in self.active_connections[channel]:
                    try:
                        await ws.send_text(message_str)
                        print(f"Message sent to websocket: {message_str}")  # Add this
                    except WebSocketDisconnect:
                        disconnected.append(ws)
                
                for ws in disconnected:
                    self.active_connections[channel].remove(ws)
            else:
                print(f"Channel {channel} not found in active connections")  # Add this
                
                
                
    async def connect_public(self, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active_public_connections.append(websocket)
            
    async def disconnect_public(self, websocket: WebSocket):
        async with self.lock:
            if websocket in self.active_public_connections:
                self.active_public_connections.remove(websocket)

    async def broadcast_notification(self, message: dict):
        async with self.lock:
            print(f"Broadcasting to {len(self.active_public_connections)} public connections")  # Debug
            disconnected = []
            message_str = json.dumps(message)
            for ws in self.active_public_connections:
                try:
                    await ws.send_text(message_str)
                    print(f"Broadcast message sent: {message_str}")  # Debug
                except WebSocketDisconnect:
                    disconnected.append(ws)
            
            for ws in disconnected:
                self.active_public_connections.remove(ws)

# Single shared instance
websocket_manager = ConnectionManager()