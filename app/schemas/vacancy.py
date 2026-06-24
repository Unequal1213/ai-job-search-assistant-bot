"""Schemas for vacancy analysis results."""

from pydantic import BaseModel


class VacancyAnalysis(BaseModel):
    """Deterministic analysis result for a vacancy text."""

    detected_role: str
    seniority_level: str
    required_skills: list[str]
    matching_keywords: list[str]
    recommendation: str
