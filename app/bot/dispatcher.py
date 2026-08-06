"""Dispatcher setup for Telegram handlers."""

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation

from app.handlers.commands import router as commands_router


def create_dispatcher() -> Dispatcher:
    """Create a user/chat-keyed FSM boundary with per-key event isolation."""
    dispatcher = Dispatcher(
        storage=MemoryStorage(), events_isolation=SimpleEventIsolation()
    )
    dispatcher.include_router(commands_router)
    return dispatcher
