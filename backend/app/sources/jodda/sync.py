"""Sincronização com a Jodda AI.

- Pedidos: carga histórica por intervalo (inicio/fim, paginada) e, depois, só os pedidos novos ou
  alterados (atualizados_desde = maior atualizado_em já recebido; pode repetir, nunca pula).
- Resumos: vendas do mês e de hoje (os mesmos números do painel da Jodda: lucro já com Ads,
  previsão do mês) e Ads do mês por conta, guardados em jodda_snapshots.
Cada pedido novo publica um evento para a TV atualizar na hora.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from app.config import TZ, get_settings
from app.db import SessionLocal
from app.models import JoddaSnapshot, OrderLine
from app.realtime import broadcaster
from app.sources.jodda.client import JoddaError, jodda
from app.state import get_state, set_state
from app.utils import now_utc, to_cents

log = logging.getLogger(__name__)

PAGE = 100
MONEY = {"total": "total_c", "comissao": "comissao_c", "frete": "frete_c", "desconto": "desconto_c",
         "custo": "custo_c", "imposto": "imposto_c", "lucro": "lucro_c", "repasse": "repasse_c"}
SUMMARIES = {
    "vendas_mes": ("/vendas/resumo", {"periodo": "mes_atual", "incluir_serie_diaria": True, "incluir_top_produtos": 5}),
    "vendas_hoje": ("/vendas/resumo", {"periodo": "hoje", "incluir_serie_diaria": False, "incluir_top_produtos": 0}),
    "ads_mes": ("/ads/resumo", {"periodo": "mes_atual", "nivel": "conta"}),
}


def _parse_ts(value: str | None, day: date) -> datetime:
    if value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
            return dt.astimezone(TZ)
        except ValueError:
            pass
    return datetime.combine(day, datetime.min.time(), tzinfo=TZ)


def _values(p: dict) -> dict:
    day = date.fromisoformat(str(p["data"])[:10])
    out = {
        "marketplace": p.get("marketplace") or "?",
        "conta": p.get("conta"),
        "order_key": str(p.get("numero_loja") or p.get("numero")),
        "numero_loja": p.get("numero_loja"),
        "numero": p.get("numero"),
        "status": p.get("status") or "Aprovado",
        "day": day,
        "sale_ts": _parse_ts(p.get("data_hora"), day),
        "updated_at_jodda": p.get("atualizado_em"),
        "sku": p.get("sku") or "?",
        "descricao": p.get("descricao"),
        "quantidade": int(p.get("quantidade") or 1),
        "logistica": p.get("logistica"),
        "uf": p.get("uf"),
        "raw": p,
    }
    for src, dst in MONEY.items():
        out[dst] = to_cents(p.get(src)) or 0
    return out


async def upsert_lines(rows: list[dict]) -> tuple[int, int]:
    """Grava/atualiza linhas de pedido. Retorna (novas, atualizadas)."""
    if not rows:
        return 0, 0
    vals = [_values(r) for r in rows if r.get("data") and (r.get("numero_loja") or r.get("numero"))]
    new = updated = 0
    async with SessionLocal() as session:
        keys = {(v["marketplace"], v["order_key"], v["sku"]) for v in vals}
        existing = {}
        for mk in {k[0] for k in keys}:
            ok = [k[1] for k in keys if k[0] == mk]
            for row in (await session.execute(select(OrderLine).where(
                    OrderLine.marketplace == mk, OrderLine.order_key.in_(ok)))).scalars():
                existing[(row.marketplace, row.order_key, row.sku)] = row
        for v in vals:
            row = existing.get((v["marketplace"], v["order_key"], v["sku"]))
            if row is None:
                row = OrderLine(**v)
                session.add(row)
                existing[(v["marketplace"], v["order_key"], v["sku"])] = row
                new += 1
            else:
                for k, val in v.items():
                    setattr(row, k, val)
                updated += 1
        await session.commit()
    return new, updated


async def _paged(params: dict) -> list[dict]:
    rows, page = [], 1
    while True:
        data = await jodda.get("/pedidos", {**params, "por_pagina": PAGE, "pagina": page})
        batch = data.get("pedidos") or []
        rows.extend(batch)
        if not batch or page * PAGE >= int(data.get("total") or 0):
            return rows
        page += 1


def _max_updated(rows: list[dict], current: str | None) -> str | None:
    stamps = [r["atualizado_em"] for r in rows if r.get("atualizado_em")]
    if current:
        stamps.append(current)
    return max(stamps) if stamps else None


async def backfill(d_from: date, d_to: date) -> dict:
    """Carga histórica mês a mês (aprovados e cancelados)."""
    total_new = total_upd = 0
    cursor = await get_state("orders_cursor")
    start = d_from
    while start <= d_to:
        end = min(d_to, (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1))
        rows = await _paged({"inicio": start.isoformat(), "fim": end.isoformat(), "status": "Todos"})
        n, u = await upsert_lines(rows)
        total_new += n
        total_upd += u
        cursor = _max_updated(rows, cursor)
        log.info("Carga %s a %s: %d linhas (%d novas)", start, end, len(rows), n)
        start = end + timedelta(days=1)
    if cursor:
        await set_state("orders_cursor", cursor)
    await set_state("backfill_done", {"from": d_from.isoformat(), "to": d_to.isoformat(), "at": now_utc().isoformat()})
    return {"novas": total_new, "atualizadas": total_upd, "cursor": cursor}


async def sync_orders() -> dict:
    """Pedidos novos ou alterados desde o último cursor."""
    cursor = await get_state("orders_cursor")
    if not cursor:
        s = get_settings()
        return await backfill(date.fromisoformat(s.backfill_from), now_utc().astimezone(TZ).date())
    rows = await _paged({"atualizados_desde": cursor, "status": "Todos"})
    n, u = await upsert_lines(rows)
    new_cursor = _max_updated(rows, cursor)
    if new_cursor != cursor:
        await set_state("orders_cursor", new_cursor)
    await set_state("orders_last", {"novas": n, "atualizadas": u, "at": now_utc().isoformat()})
    if n or u:
        broadcaster.publish("sale" if n else "metrics", {"novas": n, "atualizadas": u})
    return {"novas": n, "atualizadas": u, "cursor": new_cursor}


async def refresh_summaries(keys: list[str] | None = None) -> dict:
    done = {}
    for key in keys or list(SUMMARIES):
        path, params = SUMMARIES[key]
        data = await jodda.get(path, params)
        async with SessionLocal() as session:
            row = await session.get(JoddaSnapshot, key)
            if row is None:
                session.add(JoddaSnapshot(key=key, data=data))
            else:
                row.data = data
                row.fetched_at = now_utc()
            await session.commit()
        done[key] = True
    await set_state("summaries_last", {"at": now_utc().isoformat()})
    broadcaster.publish("metrics", {"reason": "summaries"})
    return done


async def _loop(name: str, fn, interval: int) -> None:
    while True:
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except JoddaError as exc:
            log.warning("%s: %s", name, exc)
        except Exception:  # noqa: BLE001
            log.exception("%s falhou", name)
        await asyncio.sleep(interval)


async def orders_loop() -> None:
    await _loop("pedidos", sync_orders, get_settings().orders_interval_seconds)


async def summaries_loop() -> None:
    await asyncio.sleep(5)
    await _loop("resumos", refresh_summaries, get_settings().summary_interval_seconds)


async def order_count() -> int:
    async with SessionLocal() as session:
        return (await session.execute(select(func.count()).select_from(OrderLine))).scalar_one()
