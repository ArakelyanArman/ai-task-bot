import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.events import EVENTS_CHANNEL


logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, message: str) -> None:
        failed_connections: set[WebSocket] = set()
        for websocket in self.connections:
            try:
                await websocket.send_text(message)
            except (ConnectionError, RuntimeError):
                failed_connections.add(websocket)
        for websocket in failed_connections:
            self.disconnect(websocket)


manager = ConnectionManager()


async def subscribe_to_events() -> None:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await manager.broadcast(message["data"])
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.close()
        await redis.aclose()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
