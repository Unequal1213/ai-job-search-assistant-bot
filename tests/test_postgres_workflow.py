"""PostgreSQL-only transaction, persistence, and race proofs."""

import asyncio
import os

import pytest
from sqlalchemy import func, select, text

from app.core.errors import ErrorCategory
from app.db.models import (
    TelegramActor,
    UsageWindow,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStatus,
)
from app.db.repositories.workflow import WorkflowRepository
from app.db.session import (
    create_database_engine,
    create_session_factory,
)
from tests.support import BlockingVacancyProvider, workflow_service

pytestmark = pytest.mark.postgres

VACANCY = "Synthetic Junior Python vacancy with FastAPI and PostgreSQL."


@pytest.fixture
async def postgres_engine():
    """Use only an explicitly supplied disposable migrated test database."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE workflow_events, usage_windows, workflow_runs, "
                "telegram_actors RESTART IDENTITY CASCADE"
            )
        )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_actor_uniqueness_isolation_and_restart(postgres_engine) -> None:
    service = workflow_service(postgres_engine)
    first = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=100,
        vacancy_text=VACANCY,
    )
    second = await service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=20,
        telegram_update_id=101,
        vacancy_text=VACANCY,
    )
    await postgres_engine.dispose()

    database_url = os.environ["TEST_DATABASE_URL"]
    restarted_engine = create_database_engine(database_url)
    async with create_session_factory(restarted_engine)() as session:
        actors = list((await session.scalars(select(TelegramActor))).all())
        runs = list((await session.scalars(select(WorkflowRun))).all())
        events = list((await session.scalars(select(WorkflowEvent))).all())
        assert len(actors) == 2
        assert {
            (actor.telegram_user_id, actor.telegram_chat_id) for actor in actors
        } == {
            (1, 10),
            (1, 20),
        }
        assert {run.id for run in runs} == {first.workflow_id, second.workflow_id}
        assert all(run.status == WorkflowStatus.COMPLETED for run in runs)
        assert len(events) == 6
        assert VACANCY not in repr([run.result for run in runs])
        hidden = await WorkflowRepository().get_for_actor(
            session,
            actor_id=actors[1].id,
            workflow_id=first.workflow_id,
        )
        assert hidden is None
    await restarted_engine.dispose()


@pytest.mark.asyncio
async def test_postgres_concurrent_duplicate_creates_one_run_and_quota(
    postgres_engine,
) -> None:
    provider = BlockingVacancyProvider()
    service = workflow_service(postgres_engine, vacancy_provider=provider)
    arguments = {
        "telegram_user_id": 1,
        "telegram_chat_id": 10,
        "telegram_update_id": 100,
        "vacancy_text": VACANCY,
    }
    first_task = asyncio.create_task(service.analyze_vacancy(**arguments))
    await provider.started.wait()
    duplicate_task = asyncio.create_task(service.analyze_vacancy(**arguments))
    duplicate = await asyncio.wait_for(duplicate_task, timeout=5)
    provider.release.set()
    first = await asyncio.wait_for(first_task, timeout=5)

    assert first.status == WorkflowStatus.COMPLETED
    assert duplicate.duplicate is True
    assert duplicate.workflow_id == first.workflow_id
    async with create_session_factory(postgres_engine)() as session:
        assert await session.scalar(select(func.count(WorkflowRun.id))) == 1
        usage = await session.scalar(select(UsageWindow))
        assert usage is not None
        assert usage.request_count == 1
        duplicate_events = await session.scalar(
            select(func.count(WorkflowEvent.id)).where(
                WorkflowEvent.event_type == "duplicate_update"
            )
        )
        assert duplicate_events == 1


@pytest.mark.asyncio
async def test_postgres_actor_concurrency_does_not_block_another_actor(
    postgres_engine,
) -> None:
    provider = BlockingVacancyProvider()
    blocking_service = workflow_service(postgres_engine, vacancy_provider=provider)
    regular_service = workflow_service(postgres_engine)
    first_task = asyncio.create_task(
        blocking_service.analyze_vacancy(
            telegram_user_id=1,
            telegram_chat_id=10,
            telegram_update_id=1,
            vacancy_text=VACANCY,
        )
    )
    await provider.started.wait()

    concurrent = await blocking_service.analyze_vacancy(
        telegram_user_id=1,
        telegram_chat_id=10,
        telegram_update_id=2,
        vacancy_text=VACANCY,
    )
    other_actor = await asyncio.wait_for(
        regular_service.analyze_vacancy(
            telegram_user_id=2,
            telegram_chat_id=20,
            telegram_update_id=3,
            vacancy_text=VACANCY,
        ),
        timeout=5,
    )
    provider.release.set()
    first = await asyncio.wait_for(first_task, timeout=5)

    assert first.status == other_actor.status == WorkflowStatus.COMPLETED
    assert concurrent.status == WorkflowStatus.REJECTED
    assert concurrent.error_category == ErrorCategory.CONCURRENT_REQUEST
