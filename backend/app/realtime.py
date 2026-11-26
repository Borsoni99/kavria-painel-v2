"""Pub/sub em memória para o SSE da TV (processo único)."""
import asyncio
import logging

log = logging.getLogger(__name__)


class Broadcaster:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def publish(self, event: str, data: dict) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait((event, data))
            except asyncio.QueueFull:
                log.warning("Assinante SSE lento; evento %s descartado", event)


broadcaster = Broadcaster()
