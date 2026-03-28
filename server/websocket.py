"""WebSocket hub — real-time signal push to connected sidebar clients.

Clients connect to ws://localhost:7474/ws/signals
Server broadcasts whenever a new signal is generated.

Also exposes a simple ping/pong to keep connections alive.
"""

import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
ws_router = APIRouter()

# Connected clients
_clients: Set[WebSocket] = set()


@ws_router.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    logger.info("WS client connected. Total: %d", len(_clients))
    try:
        while True:
            # Keep connection alive — client can send "ping"
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        logger.info("WS client disconnected. Total: %d", len(_clients))


async def broadcast(event: str, payload: dict) -> None:
    """Push a message to all connected sidebar clients."""
    if not _clients:
        return
    message = json.dumps({"event": event, "data": payload})
    dead: Set[WebSocket] = set()
    for client in list(_clients):
        try:
            await client.send_text(message)
        except Exception:
            dead.add(client)
    _clients.difference_update(dead)


async def broadcast_loop() -> None:
    """Background task — sends a heartbeat every 30s and checks for stale connections."""
    while True:
        await asyncio.sleep(30)
        if _clients:
            await broadcast("heartbeat", {"clients": len(_clients)})
