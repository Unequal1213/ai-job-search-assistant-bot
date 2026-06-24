# AGENTS.md

## Project context

This is a portfolio project for a self-taught Junior Python Backend Developer / AI Automation Engineer.

Project name:
AI Job Search Assistant Bot

Main goal:
Build a production-style Telegram bot that helps users analyze job vacancies and generate AI-style job application support messages.

The project should demonstrate:
- Telegram bot development
- async Python
- AI automation workflow design
- clean service-layer architecture
- deterministic AI-style analysis for testability
- environment variable handling
- testing
- Docker
- GitHub Actions CI

## Tech stack

- Python
- aiogram
- Pydantic
- python-dotenv
- Pytest
- Ruff
- Docker
- GitHub Actions

## Development rules

- Do not rewrite the entire project unless explicitly requested.
- Make small, focused changes.
- Explain every changed file.
- Preserve a clean project structure.
- Use type hints.
- Follow PEP8.
- Avoid quick hacks.
- Do not commit secrets.
- Do not hardcode bot tokens, API keys, passwords, or private data.
- Use environment variables for configuration.
- Keep bot handlers separate from business logic.
- Keep AI-style logic inside app/services/.
- Prefer maintainable code over clever code.
- The first MVP must not require a real OpenAI API key.
- Use deterministic local analysis first so tests are stable and free.

## Initial MVP

Build a Telegram bot for job search assistance.

Core bot commands:
- /start
- /help
- /analyze_vacancy
- /generate_cover_letter

Initial behavior:
- /start introduces the bot.
- /help explains available commands.
- /analyze_vacancy asks the user to send a vacancy text.
- The bot analyzes the vacancy text using deterministic local rules.
- /generate_cover_letter asks the user to send a vacancy text.
- The bot generates a deterministic cover letter draft.

Vacancy analysis should return:
- detected role
- required skills
- seniority level
- matching keywords
- recommendation

Cover letter generation should return:
- a short professional cover letter draft
- based on the vacancy text
- without using external AI APIs in the first version

## Review guidelines

- Check for hardcoded secrets.
- Check that BOT_TOKEN is loaded from environment variables.
- Check that handlers stay thin.
- Check that service logic is testable without Telegram.
- Check test coverage.
- Check whether the code is understandable for a Junior Developer.
