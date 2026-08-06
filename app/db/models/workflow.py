"""Durable actor, workflow, event, and usage-window models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class WorkflowOperation(StrEnum):
    """Supported durable business operations."""

    VACANCY_ANALYSIS = "vacancy_analysis"
    COVER_LETTER = "cover_letter"


class WorkflowStatus(StrEnum):
    """Persisted workflow lifecycle statuses."""

    RECEIVED = "received"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    REJECTED = "rejected"


class TelegramActor(TimestampMixin, Base):
    """Minimal isolated Telegram user/chat identity."""

    __tablename__ = "telegram_actors"
    __table_args__ = (
        UniqueConstraint(
            "telegram_user_id",
            "telegram_chat_id",
            name="uq_telegram_actor_user_chat",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workflow_runs: Mapped[list[WorkflowRun]] = relationship(
        back_populates="actor", cascade="all, delete-orphan"
    )
    usage_windows: Mapped[list[UsageWindow]] = relationship(
        back_populates="actor", cascade="all, delete-orphan"
    )


class WorkflowRun(TimestampMixin, Base):
    """One idempotent durable execution without persistent raw input."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "telegram_chat_id",
            "telegram_update_id",
            name="uq_workflow_chat_update",
        ),
        Index("ix_workflow_actor_status", "actor_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("telegram_actors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation: Mapped[WorkflowOperation] = mapped_column(
        Enum(
            WorkflowOperation, name="workflow_operation", values_callable=_enum_values
        ),
        nullable=False,
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status", values_callable=_enum_values),
        nullable=False,
        default=WorkflowStatus.RECEIVED,
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_requested: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_used: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(64), nullable=False)
    fallback_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    actor: Mapped[TelegramActor] = relationship(back_populates="workflow_runs")
    events: Mapped[list[WorkflowEvent]] = relationship(
        back_populates="workflow_run",
        cascade="all, delete-orphan",
        order_by="WorkflowEvent.created_at",
    )


class WorkflowEvent(Base):
    """Append-only audit event restricted to safe metadata."""

    __tablename__ = "workflow_events"
    __table_args__ = (
        Index("ix_workflow_event_run_created", "workflow_run_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    workflow_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[WorkflowStatus | None] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status", values_callable=_enum_values),
        nullable=True,
    )
    to_status: Mapped[WorkflowStatus | None] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status", values_callable=_enum_values),
        nullable=True,
    )
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON_VALUE, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="events")


class UsageWindow(Base):
    """Restart-safe per-actor, per-operation fixed-window quota."""

    __tablename__ = "usage_windows"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "operation", name="uq_usage_window_actor_operation"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("telegram_actors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation: Mapped[WorkflowOperation] = mapped_column(
        Enum(
            WorkflowOperation, name="workflow_operation", values_callable=_enum_values
        ),
        nullable=False,
    )
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    actor: Mapped[TelegramActor] = relationship(back_populates="usage_windows")
