"""Minimal async entrypoint for the Telegram bot application."""

import asyncio

from app.bot.dispatcher import create_dispatcher
from app.config import get_settings


async def main() -> None:
    """Prepare the bot application without starting Telegram polling yet."""
    settings = get_settings()
    create_dispatcher()

    if not settings.bot_token:
        print("BOT_TOKEN is not set. Telegram polling is not started.")
        return

    print("BOT_TOKEN is configured. Telegram polling will be added later.")


if __name__ == "__main__":
    asyncio.run(main())
