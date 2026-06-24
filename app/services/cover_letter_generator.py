"""Deterministic cover letter generation service."""

from app.services.vacancy_analyzer import analyze_vacancy


def generate_cover_letter(vacancy_text: str) -> str:
    """Generate a short deterministic cover letter draft from vacancy text."""
    analysis = analyze_vacancy(vacancy_text)
    role = analysis.detected_role
    skills = _format_skills(analysis.required_skills)

    return (
        "Dear Hiring Manager,\n\n"
        f"I would like to apply for the {role} position. "
        f"My experience with {skills} matches the key requirements in your "
        "vacancy. I am motivated to contribute clean, reliable solutions and "
        "continue growing in a professional engineering environment.\n\n"
        "Thank you for your consideration."
    )


def _format_skills(required_skills: list[str]) -> str:
    if not required_skills:
        return "relevant technical skills"

    return ", ".join(required_skills[:3])
