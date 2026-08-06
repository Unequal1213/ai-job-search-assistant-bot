import asyncio

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings
from app.providers import (
    DeterministicCoverLetterProvider,
    DeterministicVacancyAnalysisProvider,
)


def test_settings_are_typed_validated_and_secret_safe() -> None:
    settings = Settings(
        _env_file=None,
        bot_token="synthetic-token",
        database_url="postgresql+asyncpg://user:synthetic@localhost/test",
        environment=Environment.TEST,
        max_vacancy_text_chars=500,
    )

    assert settings.workflow_limits.max_vacancy_text_chars == 500
    assert "synthetic-token" not in repr(settings)
    assert "synthetic@" not in repr(settings)


def test_settings_reject_unsafe_limit_values() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://user:synthetic@localhost/test",
            max_active_workflows_per_actor=0,
        )


def test_deterministic_provider_metadata_is_honest() -> None:
    vacancy = asyncio.run(
        DeterministicVacancyAnalysisProvider("rules-v1").analyze(
            "Junior Python role with FastAPI"
        )
    )
    cover_letter = asyncio.run(
        DeterministicCoverLetterProvider("rules-v1").generate(
            "Junior Python role with FastAPI"
        )
    )

    assert vacancy.metadata.model_dump() == {
        "provider_requested": "deterministic",
        "provider_used": "deterministic",
        "provider_kind": "offline_rules",
        "provider_version": "rules-v1",
        "fallback_used": False,
    }
    assert cover_letter.metadata == vacancy.metadata
    assert "token" not in vacancy.metadata.model_dump()
