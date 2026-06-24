# ai-job-search-assistant-bot
Telegram bot for AI-style job vacancy analysis and cover letter generation.

## MVP commands

- `/start` - introduces the bot.
- `/help` - explains available commands.
- `/analyze_vacancy` - asks the user to send vacancy text for deterministic analysis.
- `/generate_cover_letter` - asks the user to send vacancy text for a cover letter draft.

The current MVP uses deterministic local services only. It does not require
OpenAI credentials or external AI APIs.
