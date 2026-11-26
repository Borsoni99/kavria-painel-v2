"""Cliente da API da Jodda AI (https://api.joddaia.com.br/v1): só leitura, chave Bearer.

Limite da Jodda: 60 chamadas/minuto por chave. O cliente espaça as chamadas (1,1 s no mínimo)
e, num 429, espera o Retry-After antes de tentar de novo. Erros 502/503 também são repetidos.
"""
import asyncio
import logging
import time

import httpx

from app.config import get_settings
from app.health import health

log = logging.getLogger(__name__)

MIN_INTERVAL = 1.1
RETRIES = 4


class JoddaError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"Jodda {status} {code}: {message}")
        self.status = status
        self.code = code


class JoddaClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._last = 0.0

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            s = get_settings()
            self._client = httpx.AsyncClient(
                base_url=s.jodda_api_base, timeout=60,
                headers={"Authorization": f"Bearer {s.jodda_api_key}", "Accept": "application/json"},
            )
        return self._client

    async def get(self, path: str, params: dict | None = None) -> dict:
        if not get_settings().jodda_api_key:
            raise JoddaError(401, "SEM_CHAVE", "JODDA_API_KEY não configurada no .env")
        clean = {k: (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in (params or {}).items() if v is not None}
        for attempt in range(1, RETRIES + 1):
            async with self._lock:  # uma chamada por vez, espaçadas: respeita 60/min
                wait = MIN_INTERVAL - (time.monotonic() - self._last)
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    resp = await self._http().get(path, params=clean)
                except httpx.HTTPError as exc:
                    self._last = time.monotonic()
                    if attempt == RETRIES:
                        health.error(f"Jodda inacessível: {exc}")
                        raise JoddaError(0, "REDE", str(exc)) from exc
                    await asyncio.sleep(2 * attempt)
                    continue
                self._last = time.monotonic()
            if resp.status_code == 200:
                health.ok()
                return resp.json()
            try:
                body = resp.json()
            except ValueError:
                body = {}
            code, message = body.get("code", "HTTP"), body.get("error", resp.text[:200])
            if resp.status_code == 429 or resp.status_code in (502, 503):
                if attempt < RETRIES:
                    delay = float(resp.headers.get("Retry-After") or 5 * attempt)
                    log.warning("Jodda %s %s; nova tentativa em %.0fs", resp.status_code, code, delay)
                    await asyncio.sleep(delay)
                    continue
            health.error(f"Jodda {resp.status_code} {code}: {message}", reauth=resp.status_code in (401, 403))
            raise JoddaError(resp.status_code, code, message)
        raise JoddaError(0, "ESGOTADO", "tentativas esgotadas")

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


jodda = JoddaClient()
