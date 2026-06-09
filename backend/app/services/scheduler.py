"""
Background scheduler.

Runs an initial refresh on startup, then re-runs the intelligence pipeline on a
fixed interval (REFRESH_INTERVAL_SECONDS). Each cycle broadcasts the new state
to all connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import logging

from ..config import settings
from . import engine

log = logging.getLogger("pwin.scheduler")


class Scheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def _loop(self) -> None:
        # Initial refresh immediately on boot
        try:
            await engine.refresh_all(broadcast=True)
        except Exception as exc:  # noqa: BLE001
            log.exception("Initial refresh failed: %s", exc)

        interval = max(60, settings.REFRESH_INTERVAL_SECONDS)
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set():
                break
            try:
                await engine.refresh_all(broadcast=True)
            except Exception as exc:  # noqa: BLE001
                log.exception("Scheduled refresh failed: %s", exc)

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop())
            log.info("Scheduler started (interval=%ss).", settings.REFRESH_INTERVAL_SECONDS)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        log.info("Scheduler stopped.")


scheduler = Scheduler()
