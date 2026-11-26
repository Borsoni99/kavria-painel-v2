"""Dados da TV: snapshot do mês + atualização ao vivo via SSE.

O hub recalcula o snapshot quando chega uma venda/alteração (com debounce) e a cada 60 s
(para virar o dia e atualizar o indicador de sincronização). Todas as TVs conectadas
recebem o mesmo snapshot, calculado uma única vez.
Acesso: sessão do admin ou `?key=TV_ACCESS_KEY` (o EventSource não envia cabeçalhos).
"""
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.api.auth import is_admin
from app.config import FRONTEND_DIST, get_settings
from app.db import SessionLocal
from app.finance.tv_data import tv_data
from app.health import health
from app.realtime import broadcaster
from app.security import constant_time_equals
from app.state import get_state
from app.utils import now_utc

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tv")

REFRESH_SECONDS = 60
DEBOUNCE_SECONDS = 1.5


def authorized(request: Request, key: str | None) -> bool:
    if is_admin(request):
        return True
    expected = get_settings().tv_access_key
    return bool(expected) and bool(key) and constant_time_equals(key, expected)


def build_id() -> str:
    """Muda quando o frontend é recompilado: a TV recarrega sozinha para pegar a versão nova."""
    try:
        return str(int((FRONTEND_DIST / "index.html").stat().st_mtime))
    except OSError:
        return "dev"


async def sync_status() -> dict:
    orders = await get_state("orders_last") or {}
    summaries = await get_state("summaries_last") or {}
    candidates = [t for t in (health.last_ok_at.isoformat() if health.last_ok_at else None,
                              orders.get("at"), summaries.get("at")) if t]
    return {
        "last_sync_at": max(candidates) if candidates else None,
        "consecutive_errors": health.consecutive_errors,
        "last_error": health.last_error if health.consecutive_errors else None,
        "account_connected": bool(get_settings().jodda_api_key),
        "reauth_required": health.reauth_required,
        "workers_enabled": get_settings().workers_enabled,
    }


class TvHub:
    def __init__(self) -> None:
        self.snapshot: dict | None = None
        self.version = 0
        self._changed = asyncio.Event()
        self._lock = asyncio.Lock()

    async def compute(self) -> None:
        now = now_utc()
        async with SessionLocal() as session:
            data = await tv_data(session, now)
        data["status"] = await sync_status()
        data["build"] = build_id()
        data["server_time"] = now.isoformat()
        self.snapshot = data
        self.version += 1
        previous, self._changed = self._changed, asyncio.Event()
        previous.set()

    async def current(self) -> tuple[dict, int]:
        if self.snapshot is None:
            async with self._lock:
                if self.snapshot is None:
                    await self.compute()
        return self.snapshot, self.version

    async def wait_change(self, version: int, timeout: float) -> None:
        if self.version != version:
            return
        event = self._changed
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except TimeoutError:
            pass

    async def run(self) -> None:
        queue = broadcaster.subscribe()
        log.info("Hub da TV iniciado")
        while True:
            try:
                try:
                    await asyncio.wait_for(queue.get(), timeout=REFRESH_SECONDS)
                    # Várias notificações seguidas (pedido + envio + pagamento) viram um cálculo só
                    await asyncio.sleep(DEBOUNCE_SECONDS)
                    while not queue.empty():
                        queue.get_nowait()
                except TimeoutError:
                    pass
                await self.compute()
            except asyncio.CancelledError:
                broadcaster.unsubscribe(queue)
                raise
            except Exception:  # noqa: BLE001
                log.exception("Erro ao atualizar o snapshot da TV")
                await asyncio.sleep(5)


hub = TvHub()


@router.get("/snapshot")
async def snapshot(request: Request, key: str | None = None):
    if not authorized(request, key):
        raise HTTPException(401, "chave da TV inválida")
    data, _ = await hub.current()
    return data


@router.get("/stream")
async def stream(request: Request, key: str | None = None):
    if not authorized(request, key):
        raise HTTPException(401, "chave da TV inválida")

    async def events():
        sent = -1
        while True:
            data, version = await hub.current()
            if version != sent:
                sent = version
                yield {"event": "snapshot", "data": json.dumps(data, ensure_ascii=False, default=str)}
            await hub.wait_change(version, timeout=20)
            if await request.is_disconnected():
                break

    # Ping a cada 15 s: Cloudflare/ngrok derrubam conexões ociosas (~100 s). Vai como evento
    # nomeado com dados (não como comentário SSE), porque o ngrok descarta comentários.
    return EventSourceResponse(
        events(), ping=15,
        ping_message_factory=lambda: ServerSentEvent(event="ping", data=now_utc().isoformat()),
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
