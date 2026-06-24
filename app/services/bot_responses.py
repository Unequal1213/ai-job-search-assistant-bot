"""Text response helpers used by Telegram handlers."""

from app.schemas.vacancy import VacancyAnalysis


def get_start_text() -> str:
    """Return the /start command response."""
    return (
        "Hello! I am your AI Job Search Assistant Bot.\n\n"
        "I can analyze vacancy text and help prepare a short cover letter draft "
        "using deterministic local rules."
    )


def get_help_text() -> str:
    """Return the /help command response."""
    return (
        "Available commands:\n"
        "/start - introduce the bot\n"
        "/help - show available commands\n"
        "/analyze_vacancy - analyze a vacancy text\n"
        "/generate_cover_letter - create a short cover letter draft"
    )


def get_analyze_vacancy_prompt() -> str:
    """Return the prompt for vacancy analysis input."""
    return "Please send the vacancy text you want me to analyze."


def get_cover_letter_prompt() -> str:
    """Return the prompt for cover letter generation input."""
    return "Please send the vacancy text for the cover letter draft."


def format_vacancy_analysis_response(analysis: VacancyAnalysis) -> str:
    """Format vacancy analysis for Telegram output."""
    required_skills = ", ".join(analysis.required_skills) or "Not detected"
    matching_keywords = ", ".join(analysis.matching_keywords) or "Not detected"

    return (
        "Vacancy analysis:\n"
        f"Detected role: {analysis.detected_role}\n"
        f"Seniority level: {analysis.seniority_level}\n"
        f"Required skills: {required_skills}\n"
        f"Matching keywords: {matching_keywords}\n"
        f"Recommendation: {analysis.recommendation}"
    )


def format_cover_letter_response(cover_letter: str) -> str:
    """Format a cover letter draft for Telegram output."""
    return f"Cover letter draft:\n\n{cover_letter}"
