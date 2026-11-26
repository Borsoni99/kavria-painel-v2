from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import SyncState
from app.utils import now_utc


async def get_state(key: str, default=None, session: AsyncSession | None = None):
    if session is None:
        async with SessionLocal() as s:
            return await get_state(key, default, s)
    row = await session.get(SyncState, key)
    return default if row is None else row.value


async def set_state(key: str, value) -> None:
    async with SessionLocal() as session:
        row = await session.get(SyncState, key)
        if row is None:
            session.add(SyncState(key=key, value=value))
        else:
            row.value = value
            row.updated_at = now_utc()
        await session.commit()
