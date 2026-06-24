"""Dispatcher setup for Telegram handlers."""

from aiogram import Dispatcher

from app.handlers.commands import router as commands_router


def create_dispatcher() -> Dispatcher:
    """Create and configure the aiogram dispatcher."""
    dispatcher = Dispatcher()
    dispatcher.include_router(commands_router)
    return dispatcher
