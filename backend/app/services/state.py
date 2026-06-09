"""
In-memory live state + WebSocket connection manager.

Holds the latest computed snapshot for every province plus the national summary
and active alerts, so REST reads are instant and WebSocket clients can be
broadcast to on each refresh. The database keeps the durable history; this is
the hot cache that powers the command center in real time.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

log = logging.getLogger("pwin.state")


class LiveState:
    def __init__(self) -> None:
        self.provinces: dict[str, dict[str, Any]] = {}   # name -> snapshot
        self.alerts: list[dict[str, Any]] = []
        self.national: dict[str, Any] = {}
        self.last_refresh: str | None = None
        self.refreshing: bool = False

    def province_index_light(self) -> dict[str, dict]:
        """Minimal index for NL queries."""
        return {
            name: {"condition": s["condition"], "event": s.get("event")}
            for name, s in self.provinces.items()
        }


state = LiveState()


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts JSON messages."""

    def __init__(self) -> None:
        self.active: set[Any] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
        log.info("WS client connected (%d active)", len(self.active))

    async def disconnect(self, ws) -> None:
        async with self._lock:
            self.active.discard(ws)
        log.info("WS client disconnected (%d active)", len(self.active))

    async def broadcast(self, message: dict) -> None:
        if not self.active:
            return
        payload = json.dumps(message, default=str)
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


manager = ConnectionManager()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
