"""Thin application service around the cover-letter provider contract."""

from app.providers.base import CoverLetterProvider
from app.schemas.provider import CoverLetterResult


class CoverLetterService:
    """Execute template draft generation through an injected provider."""

    def __init__(self, provider: CoverLetterProvider) -> None:
        self._provider = provider

    async def generate(self, vacancy_text: str) -> CoverLetterResult:
        """Keep raw input in memory only for the duration of provider execution."""
        return await self._provider.generate(vacancy_text)
