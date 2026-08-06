"""Durable workflow orchestration with isolation, idempotency, and controls."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.errors import ErrorCategory, WorkflowError
from app.core.limits import WorkflowLimits
from app.core.logging import log_event
from app.db.models import WorkflowOperation, WorkflowRun, WorkflowStatus
from app.db.repositories import ActorRepository, WorkflowRepository
from app.db.session import SessionFactory
from app.schemas.workflow import WorkflowOutcome
from app.services.cover_letter_service import CoverLetterService
from app.services.rate_limit_service import RateLimitService
from app.services.vacancy_analysis_service import VacancyAnalysisService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _ProcessingContext:
    actor_id: UUID
    workflow_id: UUID


class WorkflowService:
    """Orchestrate durable runs while raw input remains process-local."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        limits: WorkflowLimits,
        provider_version: str,
        vacancy_service: VacancyAnalysisService,
        cover_letter_service: CoverLetterService,
        actor_repository: ActorRepository | None = None,
        workflow_repository: WorkflowRepository | None = None,
        rate_limit_service: RateLimitService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._limits = limits
        self._provider_version = provider_version
        self._vacancy_service = vacancy_service
        self._cover_letter_service = cover_letter_service
        self._actors = actor_repository or ActorRepository()
        self._workflows = workflow_repository or WorkflowRepository()
        self._rate_limits = rate_limit_service or RateLimitService()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def analyze_vacancy(
        self,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_update_id: int,
        vacancy_text: str,
    ) -> WorkflowOutcome:
        """Run idempotent durable vacancy analysis."""
        return await self._process(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_update_id=telegram_update_id,
            operation=WorkflowOperation.VACANCY_ANALYSIS,
            vacancy_text=vacancy_text,
        )

    async def generate_cover_letter(
        self,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_update_id: int,
        vacancy_text: str,
    ) -> WorkflowOutcome:
        """Run idempotent durable template-based draft generation."""
        return await self._process(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            telegram_update_id=telegram_update_id,
            operation=WorkflowOperation.COVER_LETTER,
            vacancy_text=vacancy_text,
        )

    async def _process(
        self,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_update_id: int,
        operation: WorkflowOperation,
        vacancy_text: str,
    ) -> WorkflowOutcome:
        started = monotonic()
        try:
            admission = await self._admit(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                telegram_update_id=telegram_update_id,
                operation=operation,
                vacancy_text=vacancy_text,
            )
        except WorkflowError:
            raise
        except IntegrityError as error:
            raise WorkflowError(ErrorCategory.DUPLICATE_UPDATE) from error
        except SQLAlchemyError as error:
            log_event(
                LOGGER,
                level=logging.ERROR,
                event="workflow_admission_failed",
                operation=operation.value,
                error_category=ErrorCategory.PERSISTENCE_ERROR.value,
            )
            raise WorkflowError(ErrorCategory.PERSISTENCE_ERROR) from error

        if isinstance(admission, WorkflowOutcome):
            return admission

        try:
            if operation == WorkflowOperation.VACANCY_ANALYSIS:
                provider_result = await self._vacancy_service.analyze(vacancy_text)
            else:
                provider_result = await self._cover_letter_service.generate(
                    vacancy_text
                )
            result = provider_result.model_dump(mode="json")
        except Exception as error:
            await self._finish_failed(admission, ErrorCategory.INTERNAL_ERROR)
            log_event(
                LOGGER,
                level=logging.ERROR,
                event="workflow_failed",
                workflow_id=admission.workflow_id,
                actor_id=admission.actor_id,
                operation=operation.value,
                status=WorkflowStatus.FAILED.value,
                error_category=ErrorCategory.INTERNAL_ERROR.value,
                latency_ms=round((monotonic() - started) * 1000),
            )
            raise WorkflowError(ErrorCategory.INTERNAL_ERROR) from error

        outcome = await self._finish_completed(admission, result)
        log_event(
            LOGGER,
            event="workflow_completed",
            workflow_id=admission.workflow_id,
            actor_id=admission.actor_id,
            operation=operation.value,
            status=WorkflowStatus.COMPLETED.value,
            input_char_count=len(vacancy_text),
            provider_used="deterministic",
            latency_ms=round((monotonic() - started) * 1000),
            telegram_update_id=telegram_update_id,
        )
        return outcome

    async def _admit(
        self,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_update_id: int,
        operation: WorkflowOperation,
        vacancy_text: str,
    ) -> WorkflowOutcome | _ProcessingContext:
        now = self._clock()
        char_count = len(vacancy_text)
        fingerprint = hashlib.sha256(vacancy_text.encode("utf-8")).hexdigest()

        async with self._session_factory() as session, session.begin():
            actor = await self._actors.get_or_create(
                session,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                now=now,
            )
            await self._actors.lock(session, actor.id)

            duplicate = await self._workflows.get_by_update_for_actor(
                session,
                actor_id=actor.id,
                telegram_chat_id=telegram_chat_id,
                telegram_update_id=telegram_update_id,
            )
            if duplicate is not None:
                await self._workflows.add_duplicate_event(session, run=duplicate)
                return self._to_outcome(duplicate, duplicate=True)

            cutoff = now - timedelta(seconds=self._limits.workflow_timeout_seconds)
            stale_runs = await self._workflows.get_stale_active(
                session, actor_id=actor.id, cutoff=cutoff
            )
            for stale_run in stale_runs:
                await self._workflows.transition(
                    session,
                    run=stale_run,
                    to_status=WorkflowStatus.FAILED,
                    now=now,
                    error_category=ErrorCategory.INTERNAL_ERROR,
                    safe_metadata={"reason": "workflow_timeout"},
                )

            active_count = await self._workflows.count_active(
                session, actor_id=actor.id
            )
            run = await self._workflows.create(
                session,
                actor_id=actor.id,
                telegram_chat_id=telegram_chat_id,
                telegram_update_id=telegram_update_id,
                operation=operation,
                input_fingerprint=fingerprint,
                input_char_count=char_count,
                provider_version=self._provider_version,
            )

            input_error = self._validate_input(operation, vacancy_text)
            if input_error is not None:
                await self._workflows.transition(
                    session,
                    run=run,
                    to_status=WorkflowStatus.REJECTED,
                    now=now,
                    error_category=input_error,
                )
                return self._to_outcome(run)

            if active_count >= self._limits.max_active_workflows_per_actor:
                await self._workflows.transition(
                    session,
                    run=run,
                    to_status=WorkflowStatus.REJECTED,
                    now=now,
                    error_category=ErrorCategory.CONCURRENT_REQUEST,
                )
                return self._to_outcome(run)

            allowed = await self._rate_limits.consume(
                session,
                actor_id=actor.id,
                operation=operation,
                now=now,
                window_seconds=self._limits.rate_limit_window_seconds,
                requests_per_window=self._limits.rate_limit_requests_per_window,
            )
            if not allowed:
                await self._workflows.transition(
                    session,
                    run=run,
                    to_status=WorkflowStatus.RATE_LIMITED,
                    now=now,
                    error_category=ErrorCategory.RATE_LIMITED,
                )
                return self._to_outcome(run)

            await self._workflows.transition(
                session,
                run=run,
                to_status=WorkflowStatus.PROCESSING,
                now=now,
            )
            return _ProcessingContext(actor_id=actor.id, workflow_id=run.id)

    async def _finish_completed(
        self, context: _ProcessingContext, result: dict[str, object]
    ) -> WorkflowOutcome:
        now = self._clock()
        try:
            async with self._session_factory() as session, session.begin():
                run = await self._workflows.lock_for_actor(
                    session,
                    actor_id=context.actor_id,
                    workflow_id=context.workflow_id,
                )
                if run is None:
                    raise WorkflowError(ErrorCategory.PERSISTENCE_ERROR)
                await self._workflows.transition(
                    session,
                    run=run,
                    to_status=WorkflowStatus.COMPLETED,
                    now=now,
                    result=result,
                )
                return self._to_outcome(run)
        except WorkflowError:
            raise
        except SQLAlchemyError as error:
            raise WorkflowError(ErrorCategory.PERSISTENCE_ERROR) from error

    async def _finish_failed(
        self, context: _ProcessingContext, category: ErrorCategory
    ) -> None:
        now = self._clock()
        try:
            async with self._session_factory() as session, session.begin():
                run = await self._workflows.lock_for_actor(
                    session,
                    actor_id=context.actor_id,
                    workflow_id=context.workflow_id,
                )
                if run is not None and run.status == WorkflowStatus.PROCESSING:
                    await self._workflows.transition(
                        session,
                        run=run,
                        to_status=WorkflowStatus.FAILED,
                        now=now,
                        error_category=category,
                    )
        except SQLAlchemyError:
            log_event(
                LOGGER,
                level=logging.ERROR,
                event="workflow_failure_persistence_failed",
                workflow_id=context.workflow_id,
                actor_id=context.actor_id,
                error_category=ErrorCategory.PERSISTENCE_ERROR.value,
            )

    def _validate_input(
        self, operation: WorkflowOperation, vacancy_text: str
    ) -> ErrorCategory | None:
        if not vacancy_text.strip():
            return ErrorCategory.INVALID_INPUT
        operation_limit = (
            self._limits.max_vacancy_text_chars
            if operation == WorkflowOperation.VACANCY_ANALYSIS
            else self._limits.max_cover_letter_context_chars
        )
        if len(vacancy_text) > min(operation_limit, self._limits.max_message_chars):
            return ErrorCategory.INPUT_TOO_LARGE
        return None

    @staticmethod
    def _to_outcome(run: WorkflowRun, *, duplicate: bool = False) -> WorkflowOutcome:
        category = (
            ErrorCategory(run.error_category)
            if run.error_category is not None
            else None
        )
        return WorkflowOutcome(
            workflow_id=run.id,
            operation=run.operation,
            status=run.status,
            result=run.result,
            error_category=category,
            duplicate=duplicate,
        )
