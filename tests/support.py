"""Synthetic test helpers for isolated workflow services."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.limits import WorkflowLimits
from app.db.models import Base
from app.db.session import (
    create_database_engine,
    create_session_factory,
)
from app.providers import (
    DeterministicCoverLetterProvider,
    DeterministicVacancyAnalysisProvider,
)
from app.schemas.provider import VacancyAnalysisResult
from app.services.cover_letter_service import CoverLetterService
from app.services.vacancy_analysis_service import VacancyAnalysisService
from app.services.workflow_service import WorkflowService


def workflow_limits(**overrides: int) -> WorkflowLimits:
    """Return conservative test limits with explicit override support."""
    values = {
        "max_vacancy_text_chars": 1_000,
        "max_cover_letter_context_chars": 1_000,
        "max_message_chars": 1_000,
        "max_active_workflows_per_actor": 1,
        "workflow_timeout_seconds": 120,
        "rate_limit_window_seconds": 60,
        "rate_limit_requests_per_window": 5,
    }
    values.update(overrides)
    return WorkflowLimits(**values)


@dataclass(slots=True)
class MutableClock:
    """Deterministic UTC clock for fixed-window boundary tests."""

    now: datetime = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


async def sqlite_engine(path: Path) -> AsyncEngine:
    """Create a disposable SQLite engine for fast non-PostgreSQL tests."""
    engine = create_database_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


def workflow_service(
    engine: AsyncEngine,
    *,
    limits: WorkflowLimits | None = None,
    clock: MutableClock | None = None,
    vacancy_provider: object | None = None,
) -> WorkflowService:
    """Wire a workflow service around deterministic or controlled providers."""
    provider = vacancy_provider or DeterministicVacancyAnalysisProvider("rules-v1")
    return WorkflowService(
        session_factory=create_session_factory(engine),
        limits=limits or workflow_limits(),
        provider_version="rules-v1",
        vacancy_service=VacancyAnalysisService(provider),  # type: ignore[arg-type]
        cover_letter_service=CoverLetterService(
            DeterministicCoverLetterProvider("rules-v1")
        ),
        clock=clock,
    )


class BlockingVacancyProvider:
    """Controlled provider that exposes admission without external calls."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self._delegate = DeterministicVacancyAnalysisProvider("rules-v1")

    async def analyze(self, vacancy_text: str) -> VacancyAnalysisResult:
        self.started.set()
        await self.release.wait()
        return await self._delegate.analyze(vacancy_text)
