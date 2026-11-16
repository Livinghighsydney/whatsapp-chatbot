from __future__ import annotations
import asyncio
from typing import AsyncIterator

_clients: set[asyncio.Queue] = set()


def push(event: str = "refresh") -> None:
    for q in list(_clients):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def stream() -> AsyncIterator[str]:
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
