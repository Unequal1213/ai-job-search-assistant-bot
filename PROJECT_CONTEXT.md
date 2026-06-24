# PROJECT_CONTEXT.md

## Project

AI Job Search Assistant Bot

## Goal

Create a portfolio-ready Telegram bot project that demonstrates async Python, Telegram bot development, AI automation workflow design, deterministic AI-style analysis, testing, Docker, and CI.

The bot will help users analyze job vacancy text and generate a simple job application cover letter draft.

## Repository

GitHub repository:
https://github.com/Unequal1213/ai-job-search-assistant-bot

## Target role

Junior Python Backend Developer / AI Automation Engineer

## Planned stack

- Python
- aiogram
- Pydantic
- python-dotenv
- Pytest
- Ruff
- Docker
- GitHub Actions

## Architecture direction

Use a clean and understandable structure:

- app/main.py
- app/config.py
- app/bot/
- app/handlers/
- app/services/
- app/schemas/

Business logic should live in app/services/ and should not be hardcoded inside Telegram handlers.

The first implementation should use deterministic local AI-style logic so tests can run without external services or API keys.

A real LLM provider can be added later behind the same service interface.

## Current status

Repository has just been created.

Next step:
Create the initial Python project foundation with config, dependency files, Ruff, Pytest, and basic deterministic service tests.

## Important rules

- Do not commit .env.
- Do not hardcode Telegram bot tokens.
- Do not require a real OpenAI API key in the MVP.
- Keep changes small and focused.
- Prefer clear code over clever abstractions.
- Tests should not require real Telegram API access.
