"""Thin application service around the vacancy provider contract."""

from app.providers.base import VacancyAnalysisProvider
from app.schemas.provider import VacancyAnalysisResult


class VacancyAnalysisService:
    """Execute vacancy analysis through an injected provider."""

    def __init__(self, provider: VacancyAnalysisProvider) -> None:
        self._provider = provider

    async def analyze(self, vacancy_text: str) -> VacancyAnalysisResult:
        """Keep raw input in memory only for the duration of provider execution."""
        return await self._provider.analyze(vacancy_text)
