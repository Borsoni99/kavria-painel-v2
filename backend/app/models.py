"""Modelo de dados do painel v2 (multicanal). Valores monetários em centavos (sufixo _c).

Os números vêm prontos da Jodda AI (comissão, frete, custo, imposto e lucro já calculados por
pedido); aqui eles são guardados para a TV, o histórico e as análises.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime
from app.utils import now_utc


class OrderLine(Base):
    """Uma linha por item de pedido, como a Jodda devolve em GET /v1/pedidos."""

    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("marketplace", "order_key", "sku"),
        Index("ix_order_lines_day", "day"),
        Index("ix_order_lines_ts", "sale_ts"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(40))
    conta: Mapped[str | None] = mapped_column(String(120))
    order_key: Mapped[str] = mapped_column(String(64))  # numero_loja (marketplace) ou numero (ERP)
    numero_loja: Mapped[str | None] = mapped_column(String(64))
    numero: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))  # Aprovado | Cancelado
    day: Mapped[date] = mapped_column(Date)
    sale_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at_jodda: Mapped[str | None] = mapped_column(String(40))
    sku: Mapped[str] = mapped_column(String(255))
    descricao: Mapped[str | None] = mapped_column(String(512))
    quantidade: Mapped[int] = mapped_column(Integer, default=1)
    total_c: Mapped[int] = mapped_column(Integer, default=0)
    comissao_c: Mapped[int] = mapped_column(Integer, default=0)
    frete_c: Mapped[int] = mapped_column(Integer, default=0)
    desconto_c: Mapped[int] = mapped_column(Integer, default=0)
    custo_c: Mapped[int] = mapped_column(Integer, default=0)
    imposto_c: Mapped[int] = mapped_column(Integer, default=0)
    lucro_c: Mapped[int] = mapped_column(Integer, default=0)
    repasse_c: Mapped[int] = mapped_column(Integer, default=0)
    logistica: Mapped[str | None] = mapped_column(String(80))
    uf: Mapped[str | None] = mapped_column(String(4))
    raw: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, onupdate=now_utc)


class JoddaSnapshot(Base):
    """Última resposta de um resumo da Jodda (ex.: vendas do mês, de hoje, Ads do mês).

    A TV usa os KPIs exatamente como a Jodda calcula (lucro já com Ads, previsão do mês)."""

    __tablename__ = "jodda_snapshots"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, onupdate=now_utc)


class MonthlyGoal(Base):
    __tablename__ = "monthly_goals"
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    goal_c: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, onupdate=now_utc)


class GoalChange(Base):
    __tablename__ = "goal_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    old_c: Mapped[int | None] = mapped_column(Integer)
    new_c: Mapped[int] = mapped_column(Integer)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON)


class SyncState(Base):
    __tablename__ = "sync_state"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc, onupdate=now_utc)
