from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.errors import ErrorCategory
from app.db.models import WorkflowOperation, WorkflowStatus
from app.handlers.commands import analyze_vacancy_text, generate_cover_letter_text
from app.schemas.workflow import WorkflowOutcome


class FakeState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=1)
        self.chat = SimpleNamespace(id=10)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class FakeWorkflowService:
    def __init__(self, outcome: WorkflowOutcome) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    async def analyze_vacancy(self, **kwargs: object) -> WorkflowOutcome:
        self.calls.append(kwargs)
        return self.outcome

    async def generate_cover_letter(self, **kwargs: object) -> WorkflowOutcome:
        self.calls.append(kwargs)
        return self.outcome


@pytest.mark.asyncio
async def test_analysis_handler_passes_minimal_ids_and_formats_result() -> None:
    outcome = WorkflowOutcome(
        workflow_id=uuid4(),
        operation=WorkflowOperation.VACANCY_ANALYSIS,
        status=WorkflowStatus.COMPLETED,
        result={
            "analysis": {
                "detected_role": "Python Backend Developer",
                "seniority_level": "Junior",
                "required_skills": ["Python"],
                "matching_keywords": ["python"],
                "recommendation": "Apply with relevant examples.",
            },
            "metadata": {
                "provider_requested": "deterministic",
                "provider_used": "deterministic",
                "provider_kind": "offline_rules",
                "provider_version": "rules-v1",
                "fallback_used": False,
            },
        },
    )
    service = FakeWorkflowService(outcome)
    message = FakeMessage("synthetic vacancy")
    state = FakeState()

    await analyze_vacancy_text(
        message,
        state,
        SimpleNamespace(update_id=99),
        service,  # type: ignore[arg-type]
    )

    assert state.cleared is True
    assert "Detected role: Python Backend Developer" in message.answers[0]
    assert service.calls == [
        {
            "telegram_user_id": 1,
            "telegram_chat_id": 10,
            "telegram_update_id": 99,
            "vacancy_text": "synthetic vacancy",
        }
    ]


@pytest.mark.asyncio
async def test_cover_letter_handler_maps_safe_domain_error() -> None:
    outcome = WorkflowOutcome(
        workflow_id=uuid4(),
        operation=WorkflowOperation.COVER_LETTER,
        status=WorkflowStatus.RATE_LIMITED,
        error_category=ErrorCategory.RATE_LIMITED,
    )
    service = FakeWorkflowService(outcome)
    message = FakeMessage("synthetic vacancy")
    state = FakeState()

    await generate_cover_letter_text(
        message,
        state,
        SimpleNamespace(update_id=100),
        service,  # type: ignore[arg-type]
    )

    assert state.cleared is True
    assert message.answers == [
        "Too many requests for this operation. Please try again later."
    ]
