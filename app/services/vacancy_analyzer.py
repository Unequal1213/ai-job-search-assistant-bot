"""Deterministic vacancy analysis service.

The first MVP deliberately avoids external AI APIs. These local rules are
simple, predictable, and easy to test.
"""

from app.schemas.vacancy import VacancyAnalysis

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Python Backend Developer": ("python", "django", "fastapi", "backend", "api"),
    "AI Automation Engineer": (
        "automation",
        "ai",
        "llm",
        "chatbot",
        "workflow",
    ),
    "Telegram Bot Developer": ("telegram", "bot", "aiogram"),
}

SENIORITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Junior": ("junior", "entry level", "trainee", "intern"),
    "Middle": ("middle", "mid-level", "2+ years", "3+ years"),
    "Senior": ("senior", "lead", "5+ years", "architect"),
}

SKILL_KEYWORDS: tuple[str, ...] = (
    "python",
    "fastapi",
    "django",
    "sql",
    "postgresql",
    "docker",
    "git",
    "pytest",
    "api",
    "asyncio",
    "aiogram",
    "telegram",
    "automation",
)

SKILL_DISPLAY_NAMES: dict[str, str] = {
    "aiogram": "aiogram",
    "api": "API",
    "asyncio": "asyncio",
    "automation": "Automation",
    "django": "Django",
    "docker": "Docker",
    "fastapi": "FastAPI",
    "git": "Git",
    "postgresql": "PostgreSQL",
    "pytest": "Pytest",
    "python": "Python",
    "sql": "SQL",
    "telegram": "Telegram",
}


def analyze_vacancy(vacancy_text: str) -> VacancyAnalysis:
    """Analyze vacancy text using deterministic keyword matching."""
    normalized_text = vacancy_text.lower()

    detected_role = _detect_role(normalized_text)
    seniority_level = _detect_seniority(normalized_text)
    required_skills = _find_required_skills(normalized_text)
    matching_keywords = _find_matching_keywords(normalized_text)
    recommendation = _build_recommendation(
        detected_role=detected_role,
        seniority_level=seniority_level,
        required_skills=required_skills,
    )

    return VacancyAnalysis(
        detected_role=detected_role,
        seniority_level=seniority_level,
        required_skills=required_skills,
        matching_keywords=matching_keywords,
        recommendation=recommendation,
    )


def _detect_role(normalized_text: str) -> str:
    for role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in normalized_text for keyword in keywords):
            return role

    return "General Software Developer"


def _detect_seniority(normalized_text: str) -> str:
    for seniority, keywords in SENIORITY_KEYWORDS.items():
        if any(keyword in normalized_text for keyword in keywords):
            return seniority

    return "Not specified"


def _find_required_skills(normalized_text: str) -> list[str]:
    return [
        SKILL_DISPLAY_NAMES[skill]
        for skill in SKILL_KEYWORDS
        if skill in normalized_text
    ]


def _find_matching_keywords(normalized_text: str) -> list[str]:
    keywords = sorted(
        {
            keyword
            for keyword_group in (
                *ROLE_KEYWORDS.values(),
                *SENIORITY_KEYWORDS.values(),
                SKILL_KEYWORDS,
            )
            for keyword in keyword_group
            if keyword in normalized_text
        }
    )
    return keywords


def _build_recommendation(
    detected_role: str,
    seniority_level: str,
    required_skills: list[str],
) -> str:
    if not required_skills:
        return (
            "Add more technical details from the vacancy before preparing "
            "an application."
        )

    skills = ", ".join(required_skills[:3])
    return (
        f"Apply as a {detected_role}. Emphasize {skills} experience"
        f" and tailor examples for a {seniority_level.lower()} level role."
    )
