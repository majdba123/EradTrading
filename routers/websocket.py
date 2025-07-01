from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_manager import websocket_manager
import json

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    print(f"New WebSocket connection for user {user_id}")  # Add this
    await websocket_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received from user {user_id}: {data}")  # Add this
    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")  # Add this
        await websocket_manager.disconnect(websocket, user_id)
        
        
@router.websocket("/ws/public")
async def public_websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect_public(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await websocket_manager.disconnect_public(websocket)