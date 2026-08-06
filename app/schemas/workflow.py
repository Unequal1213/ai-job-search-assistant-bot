"""Boundary-safe workflow request outcomes."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.errors import ErrorCategory
from app.db.models import WorkflowOperation, WorkflowStatus


class WorkflowOutcome(BaseModel):
    """Durable result safe for Telegram response rendering."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: UUID
    operation: WorkflowOperation
    status: WorkflowStatus
    result: dict[str, Any] | None = None
    error_category: ErrorCategory | None = None
    duplicate: bool = False
