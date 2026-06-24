from app.services.bot_responses import get_help_text, get_start_text


def test_start_text_introduces_bot() -> None:
    text = get_start_text()

    assert "AI Job Search Assistant Bot" in text
    assert "analyze vacancy text" in text


def test_help_text_lists_mvp_commands() -> None:
    text = get_help_text()

    assert "/start" in text
    assert "/help" in text
    assert "/analyze_vacancy" in text
    assert "/generate_cover_letter" in text
