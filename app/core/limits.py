"""Workflow input, rate, timeout, and concurrency limits."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowLimits:
    """Validated limits passed from settings to domain services."""

    max_vacancy_text_chars: int
    max_cover_letter_context_chars: int
    max_message_chars: int
    max_active_workflows_per_actor: int
    workflow_timeout_seconds: int
    rate_limit_window_seconds: int
    rate_limit_requests_per_window: int
