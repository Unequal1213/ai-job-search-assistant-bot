import json
import logging
from datetime import UTC, datetime

import pytest

from app.core.logging import log_event
from app.db.models import WorkflowOperation, WorkflowStatus
from app.db.repositories.actor import ActorRepository
from app.db.repositories.workflow import (
    InvalidStateTransitionError,
    WorkflowRepository,
)
from app.db.session import create_session_factory
from tests.support import sqlite_engine


@pytest.mark.asyncio
async def test_state_transition_writes_event_and_rejects_forbidden(tmp_path) -> None:
    engine = await sqlite_engine(tmp_path / "state.db")
    factory = create_session_factory(engine)
    actors = ActorRepository()
    workflows = WorkflowRepository()
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        actor = await actors.get_or_create(
            session, telegram_user_id=1, telegram_chat_id=10, now=now
        )
        run = await workflows.create(
            session,
            actor_id=actor.id,
            telegram_chat_id=10,
            telegram_update_id=100,
            operation=WorkflowOperation.VACANCY_ANALYSIS,
            input_fingerprint="a" * 64,
            input_char_count=4,
            provider_version="rules-v1",
        )
        await workflows.transition(
            session, run=run, to_status=WorkflowStatus.PROCESSING, now=now
        )
        await workflows.transition(
            session,
            run=run,
            to_status=WorkflowStatus.COMPLETED,
            now=now,
            result={"safe": True},
        )
        with pytest.raises(InvalidStateTransitionError):
            await workflows.transition(
                session, run=run, to_status=WorkflowStatus.PROCESSING, now=now
            )

    async with factory() as session:
        persisted = await workflows.get_for_actor(
            session, actor_id=actor.id, workflow_id=run.id, include_events=True
        )
        assert persisted is not None
        assert persisted.status == WorkflowStatus.COMPLETED
        assert [event.to_status for event in persisted.events] == [
            WorkflowStatus.RECEIVED,
            WorkflowStatus.PROCESSING,
            WorkflowStatus.COMPLETED,
        ]
    await engine.dispose()


def test_safe_logging_drops_synthetic_sensitive_marker(caplog) -> None:
    marker = "SYNTHETIC_PRIVATE_VACANCY_MARKER"
    logger = logging.getLogger("safe-log-test")
    with caplog.at_level(logging.INFO, logger="safe-log-test"):
        log_event(
            logger,
            event="workflow_completed",
            workflow_id="00000000-0000-0000-0000-000000000001",
            raw_text=marker,
            message_text=marker,
        )

    combined = " ".join(caplog.messages)
    assert marker not in combined
    payload = json.loads(caplog.messages[-1])
    assert payload["event"] == "workflow_completed"
    assert "raw_text" not in payload
