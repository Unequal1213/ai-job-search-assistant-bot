"""Async Telegram polling entrypoint with explicit database lifecycle."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncEngine

from app.bot.dispatcher import create_dispatcher
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, log_event
from app.db.session import (
    check_database_connectivity,
    create_database_engine,
    create_session_factory,
)
from app.providers import (
    DeterministicCoverLetterProvider,
    DeterministicVacancyAnalysisProvider,
)
from app.services.cover_letter_service import CoverLetterService
from app.services.vacancy_analysis_service import VacancyAnalysisService
from app.services.workflow_service import WorkflowService

LOGGER = logging.getLogger(__name__)


class PollingDispatcher(Protocol):
    """Minimal dispatcher interface needed for polling startup."""

    async def start_polling(self, bot: Bot, **workflow_data: object) -> None:
        """Start receiving updates for the provided bot."""


BotFactory = Callable[[str], Bot]
DispatcherFactory = Callable[[], PollingDispatcher]


@dataclass(frozen=True, slots=True)
class Runtime:
    """Initialized resources that must be disposed during shutdown."""

    engine: AsyncEngine
    workflow_service: WorkflowService


async def initialize_runtime(settings: Settings) -> Runtime:
    """Create the DB engine, verify connectivity, and wire offline providers."""
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        await check_database_connectivity(engine)
    except Exception:
        await engine.dispose()
        raise

    version = settings.deterministic_provider_version
    workflow_service = WorkflowService(
        session_factory=create_session_factory(engine),
        limits=settings.workflow_limits,
        provider_version=version,
        vacancy_service=VacancyAnalysisService(
            DeterministicVacancyAnalysisProvider(version)
        ),
        cover_letter_service=CoverLetterService(
            DeterministicCoverLetterProvider(version)
        ),
    )
    return Runtime(engine=engine, workflow_service=workflow_service)


async def run_bot(
    bot_token: str | None,
    bot_factory: BotFactory = Bot,
    dispatcher_factory: DispatcherFactory = create_dispatcher,
    workflow_service: WorkflowService | None = None,
) -> bool:
    """Start polling only when a token is present; always close the bot session."""
    if not bot_token:
        print("BOT_TOKEN is not set. Telegram polling is not started.")
        return False

    bot = bot_factory(bot_token)
    dispatcher = dispatcher_factory()
    print("BOT_TOKEN is configured. Starting Telegram polling.")
    try:
        if workflow_service is None:
            await dispatcher.start_polling(bot)
        else:
            await dispatcher.start_polling(bot, workflow_service=workflow_service)
        return True
    finally:
        session = getattr(bot, "session", None)
        close = getattr(session, "close", None)
        if close is not None:
            await close()


async def run_application(settings: Settings) -> bool:
    """Initialize persistence before polling and dispose it after shutdown."""
    runtime = await initialize_runtime(settings)
    try:
        token = settings.bot_token.get_secret_value() if settings.bot_token else None
        return await run_bot(token, workflow_service=runtime.workflow_service)
    finally:
        await runtime.engine.dispose()


async def main() -> None:
    """Validate settings and run the application without automatic migrations."""
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        await run_application(settings)
    except Exception:
        log_event(LOGGER, level=logging.ERROR, event="application_startup_failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
