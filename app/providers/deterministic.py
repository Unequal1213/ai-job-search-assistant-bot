"""Deterministic offline providers built on the existing local functions."""

from app.schemas.provider import (
    CoverLetterDraft,
    CoverLetterResult,
    ProviderMetadata,
    VacancyAnalysisResult,
)
from app.services.cover_letter_generator import generate_cover_letter
from app.services.vacancy_analyzer import analyze_vacancy


class DeterministicVacancyAnalysisProvider:
    """Rules-based vacancy analysis with stable metadata."""

    def __init__(self, version: str = "rules-v1") -> None:
        self._metadata = ProviderMetadata(provider_version=version)

    async def analyze(self, vacancy_text: str) -> VacancyAnalysisResult:
        """Run the existing keyword rules without external calls."""
        return VacancyAnalysisResult(
            analysis=analyze_vacancy(vacancy_text), metadata=self._metadata
        )


class DeterministicCoverLetterProvider:
    """Template-based draft provider with stable metadata."""

    def __init__(self, version: str = "rules-v1") -> None:
        self._metadata = ProviderMetadata(provider_version=version)

    async def generate(self, vacancy_text: str) -> CoverLetterResult:
        """Run the existing template generator without external calls."""
        return CoverLetterResult(
            cover_letter=CoverLetterDraft(text=generate_cover_letter(vacancy_text)),
            metadata=self._metadata,
        )
