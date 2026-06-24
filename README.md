# ai-job-search-assistant-bot
Telegram bot for AI-style job vacancy analysis and cover letter generation.

## MVP commands

- `/start` - introduces the bot.
- `/help` - explains available commands.
- `/analyze_vacancy` - asks the user to send vacancy text for deterministic analysis.
- `/generate_cover_letter` - asks the user to send vacancy text for a cover letter draft.

The current MVP uses deterministic local services only. It does not require
OpenAI credentials or external AI APIs.

## Local run

Create a local environment file:

```bash
cp .env.example .env
```

Add your real Telegram bot token to `.env`:

```bash
BOT_TOKEN=your_real_telegram_bot_token
```

Run the bot:

```bash
python -m app.main
```

If `BOT_TOKEN` is missing, the app exits cleanly without starting polling.

## Docker

Build the bot image:

```bash
docker compose build
```

Run the bot container:

```bash
docker compose up bot
```

For local bot credentials, create a `.env` file from `.env.example` and replace
the placeholder `BOT_TOKEN` value. The current app exits safely when `BOT_TOKEN`
is not set, so tests and CI do not require Telegram credentials.
