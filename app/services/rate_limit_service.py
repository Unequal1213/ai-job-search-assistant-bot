"""Persisted fixed-window per-actor rate limiting."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageWindow, WorkflowOperation


class RateLimitService:
    """Consume restart-safe quota inside the actor admission transaction."""

    async def consume(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        operation: WorkflowOperation,
        now: datetime,
        window_seconds: int,
        requests_per_window: int,
    ) -> bool:
        """Return false at quota without incrementing beyond its maximum."""
        statement = (
            select(UsageWindow)
            .where(
                UsageWindow.actor_id == actor_id,
                UsageWindow.operation == operation,
            )
            .with_for_update()
        )
        usage = await session.scalar(statement)
        if usage is None:
            session.add(
                UsageWindow(
                    actor_id=actor_id,
                    operation=operation,
                    window_started_at=now,
                    request_count=1,
                    updated_at=now,
                )
            )
            await session.flush()
            return True

        window_started_at = usage.window_started_at
        if window_started_at.tzinfo is None:
            window_started_at = window_started_at.replace(tzinfo=UTC)
        window_ends_at = window_started_at + timedelta(seconds=window_seconds)
        if now >= window_ends_at:
            usage.window_started_at = now
            usage.request_count = 1
            usage.updated_at = now
            await session.flush()
            return True

        if usage.request_count >= requests_per_window:
            return False

        usage.request_count += 1
        usage.updated_at = now
        await session.flush()
        return True
