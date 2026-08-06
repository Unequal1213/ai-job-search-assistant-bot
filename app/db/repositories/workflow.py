"""Actor-scoped workflow state and safe audit persistence."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ErrorCategory
from app.db.models import (
    WorkflowEvent,
    WorkflowOperation,
    WorkflowRun,
    WorkflowStatus,
)

ALLOWED_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.RECEIVED: frozenset(
        {
            WorkflowStatus.PROCESSING,
            WorkflowStatus.REJECTED,
            WorkflowStatus.RATE_LIMITED,
        }
    ),
    WorkflowStatus.PROCESSING: frozenset(
        {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}
    ),
}


class InvalidStateTransitionError(ValueError):
    """Raised when a durable transition is not in the explicit state graph."""


class WorkflowRepository:
    """Persist workflows and events without accepting raw input fields."""

    async def create(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        telegram_chat_id: int,
        telegram_update_id: int,
        operation: WorkflowOperation,
        input_fingerprint: str,
        input_char_count: int,
        provider_version: str,
    ) -> WorkflowRun:
        """Create a received workflow and its initial audit event."""
        run = WorkflowRun(
            actor_id=actor_id,
            telegram_chat_id=telegram_chat_id,
            telegram_update_id=telegram_update_id,
            operation=operation,
            status=WorkflowStatus.RECEIVED,
            input_fingerprint=input_fingerprint,
            input_char_count=input_char_count,
            provider_requested="deterministic",
            provider_used="deterministic",
            provider_kind="offline_rules",
            provider_version=provider_version,
            fallback_used=False,
        )
        session.add(run)
        await session.flush()
        await self.add_event(
            session,
            run=run,
            event_type="workflow_received",
            from_status=None,
            to_status=WorkflowStatus.RECEIVED,
            safe_metadata={"input_char_count": input_char_count},
        )
        return run

    async def get_for_actor(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        workflow_id: UUID,
        include_events: bool = False,
    ) -> WorkflowRun | None:
        """Retrieve a workflow only when it belongs to the supplied actor."""
        statement = select(WorkflowRun).where(
            WorkflowRun.id == workflow_id, WorkflowRun.actor_id == actor_id
        )
        if include_events:
            statement = statement.options(selectinload(WorkflowRun.events))
        return await session.scalar(statement)

    async def get_by_update_for_actor(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        telegram_chat_id: int,
        telegram_update_id: int,
    ) -> WorkflowRun | None:
        """Resolve idempotency without exposing another actor's workflow."""
        statement = select(WorkflowRun).where(
            WorkflowRun.actor_id == actor_id,
            WorkflowRun.telegram_chat_id == telegram_chat_id,
            WorkflowRun.telegram_update_id == telegram_update_id,
        )
        return await session.scalar(statement)

    async def lock_for_actor(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        workflow_id: UUID,
    ) -> WorkflowRun | None:
        """Lock one actor-owned workflow for a transactional transition."""
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.id == workflow_id, WorkflowRun.actor_id == actor_id)
            .with_for_update()
        )
        return await session.scalar(statement)

    async def count_active(self, session: AsyncSession, *, actor_id: UUID) -> int:
        """Count visible durable active workflows for one actor."""
        statement = select(func.count(WorkflowRun.id)).where(
            WorkflowRun.actor_id == actor_id,
            WorkflowRun.status.in_(
                [WorkflowStatus.RECEIVED, WorkflowStatus.PROCESSING]
            ),
        )
        return int((await session.scalar(statement)) or 0)

    async def get_stale_active(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        cutoff: datetime,
    ) -> list[WorkflowRun]:
        """Lock timed-out processing workflows for failure transitions."""
        statement = (
            select(WorkflowRun)
            .where(
                WorkflowRun.actor_id == actor_id,
                WorkflowRun.status == WorkflowStatus.PROCESSING,
                WorkflowRun.started_at < cutoff,
            )
            .with_for_update()
        )
        return list((await session.scalars(statement)).all())

    async def transition(
        self,
        session: AsyncSession,
        *,
        run: WorkflowRun,
        to_status: WorkflowStatus,
        now: datetime,
        result: dict[str, Any] | None = None,
        error_category: ErrorCategory | None = None,
        safe_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Validate and persist one state change plus an audit event atomically."""
        from_status = run.status
        if to_status not in ALLOWED_TRANSITIONS.get(from_status, frozenset()):
            raise InvalidStateTransitionError(
                f"transition_not_allowed:{from_status.value}:{to_status.value}"
            )

        run.status = to_status
        run.updated_at = now
        if to_status == WorkflowStatus.PROCESSING:
            run.started_at = now
        if to_status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.RATE_LIMITED,
            WorkflowStatus.REJECTED,
        }:
            run.completed_at = now
        if result is not None:
            run.result = result
        if error_category is not None:
            run.error_category = error_category.value

        await self.add_event(
            session,
            run=run,
            event_type="workflow_status_changed",
            from_status=from_status,
            to_status=to_status,
            safe_metadata=safe_metadata or {},
        )
        await session.flush()

    async def add_duplicate_event(
        self, session: AsyncSession, *, run: WorkflowRun
    ) -> None:
        """Audit an idempotent retry without raw Telegram payload."""
        await self.add_event(
            session,
            run=run,
            event_type="duplicate_update",
            from_status=run.status,
            to_status=run.status,
            safe_metadata={"error_category": ErrorCategory.DUPLICATE_UPDATE.value},
        )

    async def add_event(
        self,
        session: AsyncSession,
        *,
        run: WorkflowRun,
        event_type: str,
        from_status: WorkflowStatus | None,
        to_status: WorkflowStatus | None,
        safe_metadata: dict[str, Any],
    ) -> None:
        """Append an event from service-generated safe metadata only."""
        session.add(
            WorkflowEvent(
                workflow_run_id=run.id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                safe_metadata=safe_metadata,
            )
        )
        await session.flush()
