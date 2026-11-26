"""painel v2: pedidos da Jodda, resumos, metas e estado

Revision ID: 0001
Revises:
Create Date: 2026-11-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    money = ["total_c", "comissao_c", "frete_c", "desconto_c", "custo_c", "imposto_c", "lucro_c", "repasse_c"]
    op.create_table(
        "order_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marketplace", sa.String(length=40), nullable=False),
        sa.Column("conta", sa.String(length=120), nullable=True),
        sa.Column("order_key", sa.String(length=64), nullable=False),
        sa.Column("numero_loja", sa.String(length=64), nullable=True),
        sa.Column("numero", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("sale_ts", app.db.UTCDateTime(), nullable=False),
        sa.Column("updated_at_jodda", sa.String(length=40), nullable=True),
        sa.Column("sku", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.String(length=512), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        *[sa.Column(m, sa.Integer(), nullable=False) for m in money],
        sa.Column("logistica", sa.String(length=80), nullable=True),
        sa.Column("uf", sa.String(length=4), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("fetched_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marketplace", "order_key", "sku"),
    )
    op.create_index("ix_order_lines_day", "order_lines", ["day"])
    op.create_index("ix_order_lines_ts", "order_lines", ["sale_ts"])
    op.create_table(
        "jodda_snapshots",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("fetched_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "monthly_goals",
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("goal_c", sa.Integer(), nullable=False),
        sa.Column("updated_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("month"),
    )
    op.create_table(
        "goal_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("old_c", sa.Integer(), nullable=True),
        sa.Column("new_c", sa.Integer(), nullable=False),
        sa.Column("changed_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_goal_changes_month", "goal_changes", ["month"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "sync_state",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", app.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    for t in ("sync_state", "settings", "goal_changes", "monthly_goals", "jodda_snapshots", "order_lines"):
        op.drop_table(t)
