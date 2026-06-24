from app.services.cover_letter_generator import generate_cover_letter


def test_generate_cover_letter_uses_detected_role_and_skills() -> None:
    vacancy_text = (
        "Junior Python Backend Developer needed. "
        "Required skills: Python, FastAPI, SQL, Docker."
    )

    cover_letter = generate_cover_letter(vacancy_text)

    assert "Dear Hiring Manager" in cover_letter
    assert "Python Backend Developer" in cover_letter
    assert "Python, FastAPI, SQL" in cover_letter
    assert "Thank you for your consideration." in cover_letter


def test_generate_cover_letter_handles_unknown_vacancy_text() -> None:
    cover_letter = generate_cover_letter("Friendly team with flexible schedule.")

    assert "General Software Developer" in cover_letter
    assert "relevant technical skills" in cover_letter
