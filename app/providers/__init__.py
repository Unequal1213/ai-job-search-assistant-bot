"""Offline provider contracts and deterministic implementations."""

from app.providers.deterministic import (
    DeterministicCoverLetterProvider,
    DeterministicVacancyAnalysisProvider,
)

__all__ = [
    "DeterministicCoverLetterProvider",
    "DeterministicVacancyAnalysisProvider",
]
