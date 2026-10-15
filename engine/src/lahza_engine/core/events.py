"""Hodisalar shinasi: worker oqimlaridan WebSocket obunachilariga (progress, xato, tayyor)."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subs: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        with self._lock:
            self._subs.append((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subs = [(lp, s) for (lp, s) in self._subs if s is not q]

    def publish(self, type_: str, **data: Any) -> None:
        event = {"type": type_, "ts": time.time(), **data}
        with self._lock:
            subs = list(self._subs)
        for loop, q in subs:
            def _put(q: asyncio.Queue[dict[str, Any]] = q) -> None:
                if not q.full():
                    q.put_nowait(event)

            try:
                loop.call_soon_threadsafe(_put)
            except RuntimeError:
                self.unsubscribe(q)
