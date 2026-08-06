"""Minimal structured logging with an explicit safe-field allowlist."""

import json
import logging
from datetime import UTC, datetime

SAFE_LOG_FIELDS = frozenset(
    {
        "event",
        "workflow_id",
        "actor_id",
        "operation",
        "status",
        "input_char_count",
        "provider_used",
        "error_category",
        "latency_ms",
        "telegram_update_id",
    }
)


class JsonFormatter(logging.Formatter):
    """Format only the pre-sanitized message as compact JSON."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


def configure_logging(level: str) -> None:
    """Configure application logging without secret-bearing context."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)


def log_event(
    logger: logging.Logger,
    level: int = logging.INFO,
    **fields: object,
) -> None:
    """Emit a JSON event after dropping every field outside the allowlist."""
    safe_fields = {
        key: value for key, value in fields.items() if key in SAFE_LOG_FIELDS
    }
    safe_fields["timestamp"] = datetime.now(UTC).isoformat()
    logger.log(level, json.dumps(safe_fields, default=str, separators=(",", ":")))
