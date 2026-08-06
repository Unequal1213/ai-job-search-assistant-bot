"""Safe domain error categories and user-facing messages."""

from enum import StrEnum


class ErrorCategory(StrEnum):
    """Stable error categories safe to persist and expose in metrics."""

    INVALID_INPUT = "invalid_input"
    INPUT_TOO_LARGE = "input_too_large"
    RATE_LIMITED = "rate_limited"
    CONCURRENT_REQUEST = "concurrent_request"
    DUPLICATE_UPDATE = "duplicate_update"
    PERSISTENCE_ERROR = "persistence_error"
    INTERNAL_ERROR = "internal_error"


USER_ERROR_MESSAGES: dict[ErrorCategory, str] = {
    ErrorCategory.INVALID_INPUT: "Please send non-empty vacancy text.",
    ErrorCategory.INPUT_TOO_LARGE: (
        "The message is too long. Please shorten it and try again."
    ),
    ErrorCategory.RATE_LIMITED: (
        "Too many requests for this operation. Please try again later."
    ),
    ErrorCategory.CONCURRENT_REQUEST: (
        "Another request is already being processed. Please try again shortly."
    ),
    ErrorCategory.DUPLICATE_UPDATE: "This update has already been processed.",
    ErrorCategory.PERSISTENCE_ERROR: (
        "The workflow service is temporarily unavailable. Please try again later."
    ),
    ErrorCategory.INTERNAL_ERROR: (
        "The request could not be completed. Please try again later."
    ),
}


class WorkflowError(Exception):
    """Domain exception that never embeds user input or infrastructure details."""

    def __init__(self, category: ErrorCategory) -> None:
        self.category = category
        super().__init__(category.value)

    @property
    def user_message(self) -> str:
        """Return a stable safe response for Telegram users."""
        return USER_ERROR_MESSAGES[self.category]
