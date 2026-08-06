"""Repository interfaces for durable workflows."""

from app.db.repositories.actor import ActorRepository
from app.db.repositories.workflow import WorkflowRepository

__all__ = ["ActorRepository", "WorkflowRepository"]
