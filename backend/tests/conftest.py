import os
import tempfile
from pathlib import Path

# Configuração isolada ANTES de importar o app (engine e settings são criados no import).
_TMP = Path(tempfile.mkdtemp(prefix="kavria2-tests-"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}",
        "APP_SECRET": "x" * 48,
        "JODDA_API_KEY": "jda_teste",
        "JODDA_API_BASE": "https://api.jodda.test/v1",
        "BACKFILL_FROM": "2026-11-01",
        "ADMIN_PASSWORD": "senha-teste",
        "TV_ACCESS_KEY": "chave-tv",
        "WORKERS_ENABLED": "true",
        "PUBLIC_BASE_URL": "",
    }
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.db import Base, SessionLocal  # noqa: E402
from app.migrate import run_migrations  # noqa: E402
from app.sources.jodda import client as client_mod  # noqa: E402

run_migrations()
API = "https://api.jodda.test/v1"


def pytest_collection_modifyitems(items):
    # Um único event loop para a sessão: o engine aiosqlite é global.
    marker = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        if pytest_asyncio.is_async_test(item):
            item.add_marker(marker, append=False)


@pytest_asyncio.fixture(autouse=True)
async def clean_db(monkeypatch):
    async with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(delete(table))
        await session.commit()
    # Sem espera de 1,1 s entre chamadas nem backoff real nos testes
    monkeypatch.setattr(client_mod, "MIN_INTERVAL", 0)

    async def _no_sleep(*_a, **_k):
        return None

    monkeypatch.setattr(client_mod.asyncio, "sleep", _no_sleep)
    client_mod.jodda._client = None
    yield
