import asyncio
import logging
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.errors import ErrorCategory, WorkflowError
from app.db.models import (
    TelegramActor,
    UsageWindow,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStatus,
)
from app.db.session import create_session_factory
from tests.support import (
    BlockingVacancyProvider,
    MutableClock,
    sqlite_engine,
    workflow_limits,
    workflow_service,
)

VACANCY = "Junior Python Backend Developer with FastAPI, SQL and Docker."


@pytest.mark.asyncio
async def test_workflow_persists_safe_result_audit_and_no_raw_input(tmp_path) -> None:
    engine = await sqlite_engine(tmp_path / "workflow.db")
    service = workflow_service(engine)

    outcome = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=100,
        vacancy_text=VACANCY,
    )

    assert outcome.status == WorkflowStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result["metadata"]["provider_kind"] == "offline_rules"
    async with create_session_factory(engine)() as session:
        run = await session.scalar(select(WorkflowRun))
        events = list((await session.scalars(select(WorkflowEvent))).all())
        assert run is not None
        assert run.input_char_count == len(VACANCY)
        assert run.input_fingerprint != VACANCY
        assert len(run.input_fingerprint) == 64
        persisted_repr = repr(run.result) + repr(
            [event.safe_metadata for event in events]
        )
        assert VACANCY not in persisted_repr
        assert len(events) == 3
    await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_is_idempotent_and_does_not_consume_quota(tmp_path) -> None:
    engine = await sqlite_engine(tmp_path / "duplicate.db")
    service = workflow_service(
        engine, limits=workflow_limits(rate_limit_requests_per_window=1)
    )
    request = {
        "telegram_user_id": 1,
        "telegram_chat_id": 10,
        "telegram_update_id": 100,
        "vacancy_text": VACANCY,
    }

    first = await service.analyze_vacancy(**request)
    duplicate = await service.analyze_vacancy(**request)

    assert duplicate.duplicate is True
    assert duplicate.workflow_id == first.workflow_id
    assert duplicate.result == first.result
    async with create_session_factory(engine)() as session:
        assert await session.scalar(select(func.count(WorkflowRun.id))) == 1
        usage = await session.scalar(select(UsageWindow))
        assert usage is not None
        assert usage.request_count == 1
        event_types = list(
            (await session.scalars(select(WorkflowEvent.event_type))).all()
        )
        assert event_types.count("duplicate_update") == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_actor_isolation_and_independent_rate_limits(tmp_path) -> None:
    engine = await sqlite_engine(tmp_path / "isolation.db")
    service = workflow_service(
        engine, limits=workflow_limits(rate_limit_requests_per_window=1)
    )

    first = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=100,
        vacancy_text=VACANCY,
    )
    second = await service.analyze_vacancy(
        telegram_user_id=2,
        telegram_chat_id=20,
        telegram_update_id=100,
        vacancy_text=VACANCY,
    )

    assert first.status == second.status == WorkflowStatus.COMPLETED
    async with create_session_factory(engine)() as session:
        actors = list((await session.scalars(select(TelegramActor))).all())
        windows = list((await session.scalars(select(UsageWindow))).all())
        assert len(actors) == 2
        assert len(windows) == 2
        assert {window.request_count for window in windows} == {1}
    await engine.dispose()


@pytest.mark.asyncio
async def test_input_controls_reject_before_quota(tmp_path) -> None:
    engine = await sqlite_engine(tmp_path / "input.db")
    service = workflow_service(
        engine,
        limits=workflow_limits(max_vacancy_text_chars=100, max_message_chars=100),
    )

    empty = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=1,
        vacancy_text="   ",
    )
    oversized = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=2,
        vacancy_text="x" * 101,
    )

    assert empty.error_category == ErrorCategory.INVALID_INPUT
    assert oversized.error_category == ErrorCategory.INPUT_TOO_LARGE
    assert empty.status == oversized.status == WorkflowStatus.REJECTED
    async with create_session_factory(engine)() as session:
        assert await session.scalar(select(func.count(UsageWindow.id))) == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_rate_limit_boundary_and_window_reset(tmp_path) -> None:
    engine = await sqlite_engine(tmp_path / "rate.db")
    clock = MutableClock()
    service = workflow_service(
        engine,
        clock=clock,
        limits=workflow_limits(
            rate_limit_requests_per_window=1, rate_limit_window_seconds=60
        ),
    )

    first = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=1,
        vacancy_text=VACANCY,
    )
    limited = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=2,
        vacancy_text=VACANCY,
    )
    clock.now += timedelta(seconds=60)
    reset = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=3,
        vacancy_text=VACANCY,
    )

    assert first.status == reset.status == WorkflowStatus.COMPLETED
    assert limited.status == WorkflowStatus.RATE_LIMITED
    assert limited.error_category == ErrorCategory.RATE_LIMITED
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrency_limit_is_per_actor(tmp_path) -> None:
    engine = await sqlite_engine(tmp_path / "concurrency.db")
    provider = BlockingVacancyProvider()
    service = workflow_service(engine, vacancy_provider=provider)
    first_task = asyncio.create_task(
        service.analyze_vacancy(
            telegram_user_id=1,
            telegram_chat_id=10,
            telegram_update_id=1,
            vacancy_text=VACANCY,
        )
    )
    await provider.started.wait()

    concurrent = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=2,
        vacancy_text=VACANCY,
    )
    provider.release.set()
    first = await first_task

    assert first.status == WorkflowStatus.COMPLETED
    assert concurrent.status == WorkflowStatus.REJECTED
    assert concurrent.error_category == ErrorCategory.CONCURRENT_REQUEST
    await engine.dispose()


@pytest.mark.asyncio
async def test_restart_keeps_state_and_audit(tmp_path) -> None:
    database_path = tmp_path / "restart.db"
    first_engine = await sqlite_engine(database_path)
    first_service = workflow_service(first_engine)
    outcome = await first_service.generate_cover_letter(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=100,
        vacancy_text=VACANCY,
    )
    await first_engine.dispose()

    second_engine = await sqlite_engine(database_path)
    async with create_session_factory(second_engine)() as session:
        run = await session.scalar(
            select(WorkflowRun).where(WorkflowRun.id == outcome.workflow_id)
        )
        events = list(
            (
                await session.scalars(
                    select(WorkflowEvent).where(
                        WorkflowEvent.workflow_run_id == outcome.workflow_id
                    )
                )
            ).all()
        )
        assert run is not None
        assert run.status == WorkflowStatus.COMPLETED
        assert run.result == outcome.result
        assert len(events) == 3
    await second_engine.dispose()


class FailingProvider:
    async def analyze(self, vacancy_text: str) -> object:
        raise RuntimeError(vacancy_text)


@pytest.mark.asyncio
async def test_provider_failure_is_classified_without_logging_input(
    tmp_path, caplog
) -> None:
    marker = "SYNTHETIC_SENSITIVE_FAILURE_MARKER"
    engine = await sqlite_engine(tmp_path / "failure.db")
    service = workflow_service(engine, vacancy_provider=FailingProvider())

    with caplog.at_level(logging.ERROR):
        with pytest.raises(WorkflowError) as caught:
            await service.analyze_vacancy(
                telegram_user_id=1,
                telegram_chat_id=10,
                telegram_update_id=1,
                vacancy_text=marker,
            )

    assert getattr(caught.value, "category", None) == ErrorCategory.INTERNAL_ERROR
    assert marker not in " ".join(caplog.messages)
    async with create_session_factory(engine)() as session:
        run = await session.scalar(select(WorkflowRun))
        assert run is not None
        assert run.status == WorkflowStatus.FAILED
        assert run.error_category == ErrorCategory.INTERNAL_ERROR.value
    await engine.dispose()
