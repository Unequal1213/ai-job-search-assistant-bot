"""Create durable Telegram workflow tables.

Revision ID: 20260806_0001
Revises: None
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

workflow_operation = postgresql.ENUM(
    "vacancy_analysis", "cover_letter", name="workflow_operation", create_type=False
)
workflow_status = postgresql.ENUM(
    "received",
    "processing",
    "completed",
    "failed",
    "rate_limited",
    "rejected",
    name="workflow_status",
    create_type=False,
)


def upgrade() -> None:
    """Create enums, tables, foreign keys, indexes, and server defaults."""
    bind = op.get_bind()
    workflow_operation.create(bind, checkfirst=True)
    workflow_status.create(bind, checkfirst=True)

    op.create_table(
        "telegram_actors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_actors"),
        sa.UniqueConstraint(
            "telegram_user_id",
            "telegram_chat_id",
            name="uq_telegram_actor_user_chat",
        ),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_update_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", workflow_operation, nullable=False),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("input_char_count", sa.Integer(), nullable=False),
        sa.Column("provider_requested", sa.String(length=64), nullable=False),
        sa.Column("provider_used", sa.String(length=64), nullable=False),
        sa.Column("provider_kind", sa.String(length=64), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column(
            "fallback_used",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["telegram_actors.id"],
            name="fk_workflow_actor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_runs"),
        sa.UniqueConstraint(
            "telegram_chat_id",
            "telegram_update_id",
            name="uq_workflow_chat_update",
        ),
    )
    op.create_index("ix_workflow_runs_actor_id", "workflow_runs", ["actor_id"])
    op.create_index("ix_workflow_actor_status", "workflow_runs", ["actor_id", "status"])
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("from_status", workflow_status, nullable=True),
        sa.Column("to_status", workflow_status, nullable=True),
        sa.Column(
            "safe_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_workflow_event_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_events"),
    )
    op.create_index(
        "ix_workflow_event_run_created",
        "workflow_events",
        ["workflow_run_id", "created_at"],
    )
    op.create_table(
        "usage_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("operation", workflow_operation, nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["telegram_actors.id"],
            name="fk_usage_window_actor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_windows"),
        sa.UniqueConstraint(
            "actor_id", "operation", name="uq_usage_window_actor_operation"
        ),
    )
    op.create_index("ix_usage_windows_actor_id", "usage_windows", ["actor_id"])


def downgrade() -> None:
    """Remove the foundation schema from a disposable database."""
    op.drop_index("ix_usage_windows_actor_id", table_name="usage_windows")
    op.drop_table("usage_windows")
    op.drop_index("ix_workflow_event_run_created", table_name="workflow_events")
    op.drop_table("workflow_events")
    op.drop_index("ix_workflow_actor_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_actor_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_table("telegram_actors")
    bind = op.get_bind()
    workflow_status.drop(bind, checkfirst=True)
    workflow_operation.drop(bind, checkfirst=True)
