"""Application configuration loaded from environment variables."""

from functools import lru_cache
from os import getenv

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime settings for the Telegram bot application."""

    bot_token: str | None = Field(default=None, alias="BOT_TOKEN")


@lru_cache
def get_settings() -> Settings:
    """Load settings from .env and process environment variables."""
    load_dotenv()
    return Settings(BOT_TOKEN=getenv("BOT_TOKEN"))
