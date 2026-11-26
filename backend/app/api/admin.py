"""API do admin do painel v2: status da Jodda, metas mensais e parâmetros da TV."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.auth import require_admin_api
from app.config import TZ, get_settings
from app.db import SessionLocal
from app.finance.tv_data import DEFAULT_SETTINGS, get_settings_row
from app.health import health
from app.models import GoalChange, JoddaSnapshot, MonthlyGoal, OrderLine, Setting
from app.realtime import broadcaster
from app.sources.jodda.client import JoddaError, jodda
from app.state import get_state
from app.utils import now_utc, parse_brl

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin_api)])


@router.get("/status")
async def status():
    async with SessionLocal() as session:
        lines = (await session.execute(select(func.count()).select_from(OrderLine))).scalar_one()
        first_day, last_day = (await session.execute(select(func.min(OrderLine.day), func.max(OrderLine.day)))).one()
        per_mk = dict((await session.execute(
            select(OrderLine.marketplace, func.count()).group_by(OrderLine.marketplace))).all())
        snaps = {r.key: r.fetched_at.isoformat() for r in (await session.execute(select(JoddaSnapshot))).scalars()}
    return {
        "jodda_configurada": bool(get_settings().jodda_api_key),
        "workers_enabled": get_settings().workers_enabled,
        "health": health.snapshot(),
        "linhas_pedido": lines, "primeiro_dia": first_day, "ultimo_dia": last_day, "por_marketplace": per_mk,
        "pedidos_ultima_sync": await get_state("orders_last"),
        "resumos_ultima_sync": await get_state("summaries_last"),
        "carga_historica": await get_state("backfill_done"),
        "resumos": snaps,
    }


@router.get("/jodda/conta")
async def jodda_conta():
    try:
        return await jodda.get("/conta")
    except JoddaError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/sync")
async def sync_now():
    from app.sources.jodda.sync import refresh_summaries, sync_orders

    try:
        return {"pedidos": await sync_orders(), "resumos": await refresh_summaries()}
    except JoddaError as exc:
        raise HTTPException(502, str(exc)) from exc


# ---------------------------------------------------------------- metas


class GoalIn(BaseModel):
    goal: int | str


@router.get("/goals")
async def goals():
    async with SessionLocal() as session:
        rows = list((await session.execute(select(MonthlyGoal).order_by(MonthlyGoal.month.desc()))).scalars())
        changes = list((await session.execute(select(GoalChange).order_by(GoalChange.changed_at.desc()).limit(50))).scalars())
    return {
        "months": [{"month": r.month, "goal_c": r.goal_c} for r in rows],
        "changes": [{"month": c.month, "old_c": c.old_c, "new_c": c.new_c, "changed_at": c.changed_at.isoformat()} for c in changes],
        "current_month": now_utc().astimezone(TZ).strftime("%Y-%m"),
    }


@router.put("/goals/{month}")
async def set_goal(month: str, body: GoalIn):
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(400, "mês inválido, use AAAA-MM")
    try:
        cents = body.goal if isinstance(body.goal, int) else parse_brl(str(body.goal))
    except ValueError as exc:
        raise HTTPException(422, "valor inválido") from exc
    if cents <= 0:
        raise HTTPException(422, "a meta precisa ser maior que zero")
    async with SessionLocal() as session:
        row = await session.get(MonthlyGoal, month)
        session.add(GoalChange(month=month, old_c=row.goal_c if row else None, new_c=cents))
        if row is None:
            session.add(MonthlyGoal(month=month, goal_c=cents))
        else:
            row.goal_c = cents
        await session.commit()
    broadcaster.publish("metrics", {"reason": "goal"})
    return {"month": month, "goal_c": cents}


# ---------------------------------------------------------------- parâmetros da TV


class SettingsIn(BaseModel):
    margin_green_bp: int | None = None
    margin_yellow_bp: int | None = None
    sound_enabled: bool | None = None
    sound_threshold_c: int | None = None
    sound_volume: int | None = None


@router.get("/settings")
async def get_settings_api():
    async with SessionLocal() as session:
        return await get_settings_row(session)


@router.put("/settings")
async def put_settings(body: SettingsIn):
    patch = body.model_dump(exclude_none=True)
    if "sound_volume" in patch and not 0 <= patch["sound_volume"] <= 100:
        raise HTTPException(422, "volume de 0 a 100")
    async with SessionLocal() as session:
        row = await session.get(Setting, "dashboard")
        value = {**DEFAULT_SETTINGS, **((row.value if row else None) or {}), **patch}
        if row is None:
            session.add(Setting(key="dashboard", value=value))
        else:
            row.value = value
        await session.commit()
    broadcaster.publish("metrics", {"reason": "settings"})
    return value
