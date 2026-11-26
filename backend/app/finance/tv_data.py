"""Dados da TV multicanal.

KPIs do mês e de hoje: os resumos da Jodda (mesmos números do painel deles — lucro já com Ads,
margem antes do Ads, previsão do mês). Divisão por canal, gráfico diário e últimas vendas: os
pedidos guardados (lucro por canal ANTES do Ads, que a Jodda não rateia por pedido).
Valores em centavos (_c) e pontos-base (_bp).
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TZ
from app.models import JoddaSnapshot, MonthlyGoal, OrderLine, Setting
from app.utils import month_key, to_cents

CHANNELS = ["Mercado Livre", "Shopee", "Amazon", "Tiktok Shop"]
DEFAULT_SETTINGS = {
    "margin_green_bp": 2000, "margin_yellow_bp": 1000,
    "sound_enabled": True, "sound_threshold_c": 10000, "sound_volume": 80,
}
APPROVED = "Aprovado"


def bp(num: float | None, den: float | None) -> int | None:
    return round(num * 10000 / den) if num is not None and den else None


def pct_bp(value) -> int | None:
    return None if value is None else round(float(value) * 100)


async def get_settings_row(session: AsyncSession) -> dict:
    row = await session.get(Setting, "dashboard")
    return {**DEFAULT_SETTINGS, **((row.value if row else None) or {})}


async def _snap(session: AsyncSession, key: str) -> tuple[dict | None, str | None]:
    row = await session.get(JoddaSnapshot, key)
    return (row.data, row.fetched_at.isoformat()) if row else (None, None)


def _month_bounds(today: date) -> tuple[date, date]:
    first = today.replace(day=1)
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first, nxt - timedelta(days=1)


async def tv_data(session: AsyncSession, now: datetime) -> dict:
    today = now.astimezone(TZ).date()
    first, last = _month_bounds(today)
    settings = await get_settings_row(session)
    goal = await session.get(MonthlyGoal, month_key(first))
    goal_c = goal.goal_c if goal else None

    mes, mes_at = await _snap(session, "vendas_mes")
    hoje_s, _ = await _snap(session, "vendas_hoje")
    ads, _ = await _snap(session, "ads_mes")

    # --- pedidos guardados: canal, dia, feed --------------------------------
    since = min(first, today - timedelta(days=29))
    lines = list((await session.execute(
        select(OrderLine).where(OrderLine.day >= since).order_by(OrderLine.sale_ts))).scalars())
    by_ch = {c: {"faturamento_c": 0, "lucro_c": 0, "pedidos": set(), "hoje_c": 0, "hoje_pedidos": set()} for c in CHANNELS}
    daily = defaultdict(lambda: defaultdict(int))
    daily_lucro = defaultdict(int)
    cancel_month = 0
    for ln in lines:
        if ln.status != APPROVED:
            if first <= ln.day <= last:
                cancel_month += 1
            continue
        daily[ln.day][ln.marketplace] += ln.total_c
        daily_lucro[ln.day] += ln.lucro_c
        if first <= ln.day <= last:
            ch = by_ch.setdefault(ln.marketplace, {"faturamento_c": 0, "lucro_c": 0, "pedidos": set(), "hoje_c": 0, "hoje_pedidos": set()})
            ch["faturamento_c"] += ln.total_c
            ch["lucro_c"] += ln.lucro_c
            ch["pedidos"].add(ln.order_key)
            if ln.day == today:
                ch["hoje_c"] += ln.total_c
                ch["hoje_pedidos"].add(ln.order_key)

    ads_by_mk = {m["marketplace"]: m for m in ((ads or {}).get("totais") or {}).get("por_marketplace") or []}
    month_total = sum(c["faturamento_c"] for c in by_ch.values())
    channels = []
    for name, c in by_ch.items():
        a = ads_by_mk.get(name) or {}
        channels.append({
            "marketplace": name,
            "faturamento_c": c["faturamento_c"],
            "pedidos": len(c["pedidos"]),
            "lucro_c": c["lucro_c"],
            "margem_bp": bp(c["lucro_c"], c["faturamento_c"]),
            "participacao_bp": bp(c["faturamento_c"], month_total),
            "hoje_c": c["hoje_c"],
            "hoje_pedidos": len(c["hoje_pedidos"]),
            "ads_c": to_cents(a.get("gasto")) or 0,
        })
    channels.sort(key=lambda c: (CHANNELS.index(c["marketplace"]) if c["marketplace"] in CHANNELS else 99))

    rolling = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        per = daily.get(d, {})
        rolling.append({"day": d.isoformat(), "total_c": sum(per.values()), "lucro_c": daily_lucro.get(d, 0),
                        "por_canal": {c: per.get(c, 0) for c in CHANNELS}})

    # Últimas vendas (agrupa os itens de um mesmo pedido)
    feed, seen = [], set()
    for ln in reversed(lines):
        if ln.status != APPROVED or (ln.marketplace, ln.order_key) in seen:
            continue
        seen.add((ln.marketplace, ln.order_key))
        same = [x for x in lines if x.marketplace == ln.marketplace and x.order_key == ln.order_key and x.status == APPROVED]
        total = sum(x.total_c for x in same)
        lucro = sum(x.lucro_c for x in same)
        feed.append({
            "order_id": f"{ln.marketplace}:{ln.order_key}", "grupo": f"{ln.marketplace}:{ln.order_key}",
            "ts": ln.sale_ts.astimezone(TZ).isoformat(), "marketplace": ln.marketplace,
            "title": ln.descricao, "sku": ln.sku, "qtd": sum(x.quantidade for x in same),
            "bruto_c": total, "lucro_c": lucro, "margem_bp": bp(lucro, total), "logistic_type": ln.logistica,
        })
        if len(feed) >= 6:
            break

    # --- KPIs do mês (Jodda) ---------------------------------------------------
    m = mes or {}
    fat_c = to_cents(m.get("faturamento")) if mes else month_total
    ads_m = m.get("ads") or {}
    ads_c = sum(to_cents(ads_m.get(k)) or 0 for k in ("ml", "shopee", "amazon"))
    lucro_c = to_cents(m.get("lucro")) if mes else sum(c["lucro_c"] for c in by_ch.values())
    proj_c = to_cents(m.get("previsao_mes"))
    totals = {
        "faturamento_c": fat_c or 0,
        "pedidos": m.get("pedidos", sum(len(c["pedidos"]) for c in by_ch.values())),
        "ticket_medio_c": to_cents(m.get("ticket_medio")),
        "unidades": m.get("unidades"),
        "lucro_c": lucro_c,  # já descontado o Ads (Jodda)
        "lucro_antes_ads_c": (lucro_c or 0) + ads_c if mes else lucro_c,
        "margem_bp": pct_bp(m.get("margem_pct")) if mes else bp(lucro_c, fat_c),  # antes do Ads
        "margem_pos_ads_bp": pct_bp(ads_m.get("margem_pos_ads_pct")) if mes else None,
        "imposto_c": to_cents(m.get("imposto")),
        "cancelados_mes": cancel_month,
    }
    dias_restantes = (last - today).days + 1
    goal_block = {
        "goal_c": goal_c,
        "atingido_bp": bp(totals["faturamento_c"], goal_c),
        "projecao_c": proj_c,
        "projecao_bp": bp(proj_c, goal_c),
        "falta_por_dia_c": (max(0, goal_c - totals["faturamento_c"]) // dias_restantes) if goal_c and dias_restantes else None,
        "dias_restantes": dias_restantes,
    }
    h = hoje_s or {}
    hoje = {
        "bruto_c": to_cents(h.get("faturamento")) or 0,
        "vendas": h.get("pedidos", 0),
        "ticket_medio_c": to_cents(h.get("ticket_medio")),
        "lucro_c": to_cents(h.get("lucro")) or 0,
        "margem_bp": pct_bp(h.get("margem_pct")) if h.get("faturamento") else None,
    }
    at = (ads or {}).get("totais") or {}
    ads_block = {
        "disponivel": bool(ads),
        "investimento_c": to_cents(at.get("gasto_total")) or ads_c,
        "receita_ads_c": to_cents(at.get("receita_ads_total")),
        "acos_bp": pct_bp(at.get("acos_pct")),
        "roas_x100": round(float(at["roas"]) * 100) if at.get("roas") is not None else None,
        "tacos_bp": pct_bp(at.get("participacao_ads_pct")),
        "por_canal": [{"marketplace": k, "gasto_c": to_cents(v.get("gasto")) or 0} for k, v in ads_by_mk.items() if v.get("gasto")],
    }
    return {
        "month": month_key(first), "today": today.isoformat(), "settings": settings,
        "totals": totals, "goal": goal_block, "hoje": hoje, "ads": ads_block,
        "channels": channels, "rolling": rolling, "feed": feed,
        "top_produtos": (m.get("top_produtos") or [])[:5],
        "avisos": m.get("avisos") or [], "summary_at": mes_at,
    }
