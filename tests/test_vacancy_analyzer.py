from app.services.vacancy_analyzer import analyze_vacancy


def test_analyze_vacancy_detects_python_backend_role() -> None:
    vacancy_text = (
        "We are looking for a Junior Python Backend Developer. "
        "Required skills: FastAPI, SQL, Docker, Git, pytest, REST API."
    )

    result = analyze_vacancy(vacancy_text)

    assert result.detected_role == "Python Backend Developer"
    assert result.seniority_level == "Junior"
    assert result.required_skills == [
        "Python",
        "FastAPI",
        "SQL",
        "Docker",
        "Git",
        "Pytest",
        "API",
    ]
    assert "python" in result.matching_keywords
    assert "junior" in result.matching_keywords
    assert "Apply as a Python Backend Developer" in result.recommendation


def test_analyze_vacancy_detects_ai_automation_role() -> None:
    vacancy_text = (
        "Middle AI Automation Engineer needed for LLM workflow automation "
        "and chatbot integrations."
    )

    result = analyze_vacancy(vacancy_text)

    assert result.detected_role == "AI Automation Engineer"
    assert result.seniority_level == "Middle"
    assert result.required_skills == ["Automation"]
    assert "llm" in result.matching_keywords
    assert "workflow" in result.matching_keywords


def test_analyze_vacancy_handles_unknown_text() -> None:
    result = analyze_vacancy("Friendly team with flexible schedule.")

    assert result.detected_role == "General Software Developer"
    assert result.seniority_level == "Not specified"
    assert result.required_skills == []
    assert result.matching_keywords == []
    assert result.recommendation == (
        "Add more technical details from the vacancy before preparing "
        "an application."
    )
