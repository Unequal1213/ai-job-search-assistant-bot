"""Async entrypoint for the Telegram bot application."""

import asyncio
from collections.abc import Callable
from typing import Protocol

from aiogram import Bot

from app.bot.dispatcher import create_dispatcher
from app.config import get_settings


class PollingDispatcher(Protocol):
    """Minimal dispatcher interface needed for polling startup."""

    async def start_polling(self, bot: Bot) -> None:
        """Start receiving updates for the provided bot."""


BotFactory = Callable[[str], Bot]
DispatcherFactory = Callable[[], PollingDispatcher]


async def run_bot(
    bot_token: str | None,
    bot_factory: BotFactory = Bot,
    dispatcher_factory: DispatcherFactory = create_dispatcher,
) -> bool:
    """Start Telegram polling when a bot token is available."""
    if not bot_token:
        print("BOT_TOKEN is not set. Telegram polling is not started.")
        return False

    bot = bot_factory(bot_token)
    dispatcher = dispatcher_factory()

    print("BOT_TOKEN is configured. Starting Telegram polling.")
    await dispatcher.start_polling(bot)
    return True


async def main() -> None:
    """Load settings and start the Telegram bot if configured."""
    settings = get_settings()
    await run_bot(settings.bot_token)


if __name__ == "__main__":
    asyncio.run(main())
