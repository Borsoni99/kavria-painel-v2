from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

TZ = ZoneInfo("America/Sao_Paulo")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Jodda AI (fonte de todos os canais: ML, Shopee, Amazon, TikTok Shop) ---
    jodda_api_key: str = ""
    jodda_api_base: str = "https://api.joddaia.com.br/v1"
    # Primeiro dia que a carga histórica busca (a Jodda só tem dados a partir de nov/2026)
    backfill_from: str = "2026-11-01"

    public_base_url: str = ""
    app_secret: str = ""
    admin_password: str = ""
    tv_access_key: str = ""

    workers_enabled: bool = True
    # Pedidos novos/alterados (atualizados_desde) e resumos do mês: limite da Jodda é 60/min
    orders_interval_seconds: int = 60
    summary_interval_seconds: int = 120

    database_url: str = "sqlite+aiosqlite:///./data/kavria2.db"

    @property
    def resolved_database_url(self) -> str:
        """Caminhos sqlite relativos são resolvidos a partir de backend/, independente do cwd."""
        prefix = "sqlite+aiosqlite:///"
        url = self.database_url
        if url.startswith(prefix) and url[len(prefix):].startswith("./"):
            path = (BACKEND_DIR / url[len(prefix) + 2:]).resolve()
            return prefix + path.as_posix()
        return url

    @property
    def sync_database_url(self) -> str:
        """URL síncrona equivalente, usada pelo Alembic."""
        return self.resolved_database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
