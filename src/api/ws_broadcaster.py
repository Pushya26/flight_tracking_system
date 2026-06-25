import asyncio
import json
from dataclasses import asdict
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from src.core.state_store import AircraftStateStore


class WebSocketBroadcaster:
    """
    Maintains a set of active WebSocket connections.
    A background asyncio task pushes the full state snapshot every 2 seconds.
    """

    def __init__(self, store: AircraftStateStore, interval: float = 2.0):
        self._store = store
        self._interval = interval
        self._clients: Set[WebSocket] = set()
        self._task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def handle(self, ws: WebSocket) -> None:
        await self.connect(ws)
        try:
            while True:
                await ws.receive_text()  # keep connection alive; client can send pings
        except WebSocketDisconnect:
            self.disconnect(ws)

    async def _broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            if not self._clients:
                continue
            payload = json.dumps(
                [asdict(s) for s in self._store.get_all().values()]
            )
            dead: Set[WebSocket] = set()
            for ws in list(self._clients):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            self._clients -= dead

    def start(self) -> None:
        self._task = asyncio.create_task(self._broadcast_loop())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
