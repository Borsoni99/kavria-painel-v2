"""Conversões de dinheiro e datas usadas em todo o backend.

Dinheiro é sempre guardado em centavos inteiros. A API do ML devolve floats
(ex.: 14.290000000000001), então toda entrada passa por `to_cents`.
"""
import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.config import TZ


def to_cents(value) -> int | None:
    if value is None or value == "":
        return None
    dec = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(dec * 100)


def cents_to_str(cents: int | None) -> str:
    """Formata centavos em pt-BR: 123456 -> '1.234,56'."""
    if cents is None:
        return "—"
    sign = "-" if cents < 0 else ""
    reais, cent = divmod(abs(cents), 100)
    return f"{sign}{reais:,}".replace(",", ".") + f",{cent:02d}"


def parse_brl(text: str) -> int:
    """Converte '1.234,56', '1234,56', '1234.56' ou 'R$ 12,3' para centavos."""
    s = text.strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        cents = to_cents(s)
    except InvalidOperation:
        cents = None
    if cents is None:
        raise ValueError(f"valor inválido: {text!r}")
    return cents


_TZ_NO_COLON = re.compile(r"([+-]\d{2})(\d{2})$")


def parse_ml_datetime(value: str | None) -> datetime | None:
    """Datas do ML vêm em vários formatos: '...000-04:00', '...000-0400', '...811Z'.
    Retorna sempre datetime aware em UTC."""
    if not value:
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    s = _TZ_NO_COLON.sub(r"\1:\2", s)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def local_date(dt: datetime) -> date:
    """Dia em America/Sao_Paulo — todos os cortes de dia/mês do sistema usam isto."""
    return dt.astimezone(TZ).date()


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Início (inclusivo) e fim (exclusivo) de um dia de São Paulo, como datetimes aware."""
    start = datetime(day.year, day.month, day.day, tzinfo=TZ)
    return start, start + timedelta(days=1)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ml_query_datetime(dt: datetime) -> str:
    """Formato aceito nos filtros de data do /orders/search (ex.: 2026-10-01T00:00:00.000-03:00)."""
    local = dt.astimezone(TZ)
    offset = local.strftime("%z")
    return local.strftime("%Y-%m-%dT%H:%M:%S.000") + f"{offset[:3]}:{offset[3:]}"


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"
