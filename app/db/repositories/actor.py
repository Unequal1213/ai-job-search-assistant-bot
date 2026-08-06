"""Actor persistence scoped by Telegram user and chat."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TelegramActor


class ActorRepository:
    """Create, retrieve, and lock isolated Telegram actors."""

    async def get_or_create(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        now: datetime,
    ) -> TelegramActor:
        """Return one actor for a user/chat pair, safe under create races."""
        actor = await self.get_by_identity(
            session,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
        )
        if actor is None:
            candidate = TelegramActor(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                last_seen_at=now,
            )
            try:
                async with session.begin_nested():
                    session.add(candidate)
                    await session.flush()
                actor = candidate
            except IntegrityError:
                actor = await self.get_by_identity(
                    session,
                    telegram_user_id=telegram_user_id,
                    telegram_chat_id=telegram_chat_id,
                )
                if actor is None:
                    raise
        actor.last_seen_at = now
        return actor

    async def get_by_identity(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
    ) -> TelegramActor | None:
        """Retrieve an actor only by the full isolation key."""
        statement = select(TelegramActor).where(
            TelegramActor.telegram_user_id == telegram_user_id,
            TelegramActor.telegram_chat_id == telegram_chat_id,
        )
        return await session.scalar(statement)

    async def lock(self, session: AsyncSession, actor_id: UUID) -> TelegramActor:
        """Serialize admissions for one actor without blocking other actors."""
        statement = (
            select(TelegramActor).where(TelegramActor.id == actor_id).with_for_update()
        )
        actor = await session.scalar(statement)
        if actor is None:
            raise LookupError("actor_not_found")
        return actor
