"""Backup diário do banco SQLite (cópia consistente mesmo com o app gravando).

Guarda as últimas KEEP cópias em data/backups/. No servidor, os snapshots automáticos da
Lightsail copiam o disco inteiro para fora da máquina.
"""
import asyncio
import logging
import sqlite3
from datetime import timedelta
from pathlib import Path

from app.config import DATA_DIR, TZ, get_settings
from app.utils import now_utc

log = logging.getLogger(__name__)

BACKUP_DIR = DATA_DIR / "backups"
KEEP = 30
BACKUP_HOUR_LOCAL = 4


def database_path() -> Path:
    url = get_settings().resolved_database_url
    return Path(url.split(":///", 1)[1])


def backup_db(dest_dir: Path = BACKUP_DIR, keep: int = KEEP) -> Path:
    """Copia o banco com a API de backup do SQLite e apaga as cópias mais antigas."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_utc().astimezone(TZ).strftime("%Y%m%d-%H%M")
    dest = dest_dir / f"kavria-{stamp}.db"
    src = sqlite3.connect(database_path())
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    for old in sorted(dest_dir.glob("kavria-*.db"))[:-keep]:
        old.unlink(missing_ok=True)
    return dest


def seconds_until(hour: int) -> float:
    now = now_utc().astimezone(TZ)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def backup_loop() -> None:
    while True:
        await asyncio.sleep(seconds_until(BACKUP_HOUR_LOCAL))
        try:
            path = await asyncio.to_thread(backup_db)
            log.info("Backup do banco gravado em %s", path)
        except Exception:  # noqa: BLE001
            log.exception("Falha no backup do banco")
