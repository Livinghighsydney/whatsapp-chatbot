"""Lightweight SSE pub/sub for real-time dashboard updates."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

_clients: set[asyncio.Queue] = set()


def push(event: str = "refresh") -> None:
    """Call from any context (sync or async) to notify all connected dashboards."""
    for q in list(_clients):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def stream() -> AsyncIterator[str]:
    """Async generator — yields SSE-formatted strings until the client disconnects."""
    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _clients.add(q)
    try:
        yield "data: connected\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=20)
                yield f"data: {msg}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _clients.discard(q)
