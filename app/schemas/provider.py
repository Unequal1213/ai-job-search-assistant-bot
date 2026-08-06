"""Strict deterministic provider result contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.vacancy import VacancyAnalysis


class ProviderMetadata(BaseModel):
    """Auditable provider selection metadata without invented usage counts."""

    model_config = ConfigDict(extra="forbid")

    provider_requested: Literal["deterministic"] = "deterministic"
    provider_used: Literal["deterministic"] = "deterministic"
    provider_kind: Literal["offline_rules"] = "offline_rules"
    provider_version: str
    fallback_used: Literal[False] = False


class VacancyAnalysisResult(BaseModel):
    """Vacancy analysis plus provider metadata."""

    model_config = ConfigDict(extra="forbid")

    analysis: VacancyAnalysis
    metadata: ProviderMetadata


class CoverLetterDraft(BaseModel):
    """Template-based cover-letter draft."""

    model_config = ConfigDict(extra="forbid")

    text: str


class CoverLetterResult(BaseModel):
    """Cover-letter draft plus provider metadata."""

    model_config = ConfigDict(extra="forbid")

    cover_letter: CoverLetterDraft
    metadata: ProviderMetadata
