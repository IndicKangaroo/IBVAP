"""WebSocket connection manager — Phase 4.

Simple in-memory broadcast: every connected dashboard client gets
every event/incident update. Good enough for a single-instance
hackathon backend; a multi-instance production deployment would need
a shared pub/sub layer (Redis etc.) behind this instead — not needed
for the demo.
"""
from __future__ import annotations

import json
from typing import List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
