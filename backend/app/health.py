"""Saúde da conexão com o ML, em memória. Alimenta o indicador discreto da TV e o /admin."""
from dataclasses import asdict, dataclass, field
from datetime import datetime

from app.utils import now_utc


@dataclass
class ApiHealth:
    last_ok_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    consecutive_errors: int = 0
    reauth_required: bool = False
    last_webhook_at: datetime | None = None
    counters: dict = field(default_factory=dict)

    def ok(self) -> None:
        self.last_ok_at = now_utc()
        self.consecutive_errors = 0
        self.reauth_required = False

    def error(self, message: str, reauth: bool = False) -> None:
        self.last_error_at = now_utc()
        self.last_error = message[:500]
        self.consecutive_errors += 1
        if reauth:
            self.reauth_required = True

    def bump(self, key: str, n: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + n

    def snapshot(self) -> dict:
        data = asdict(self)
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data


health = ApiHealth()
