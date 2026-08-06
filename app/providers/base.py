"""Async provider protocols reserved for replaceable workflow implementations."""

from typing import Protocol

from app.schemas.provider import CoverLetterResult, VacancyAnalysisResult


class VacancyAnalysisProvider(Protocol):
    """Contract for strict vacancy-analysis results."""

    async def analyze(self, vacancy_text: str) -> VacancyAnalysisResult:
        """Analyze one in-memory vacancy text."""


class CoverLetterProvider(Protocol):
    """Contract for strict cover-letter results."""

    async def generate(self, vacancy_text: str) -> CoverLetterResult:
        """Generate one draft from in-memory vacancy text."""
