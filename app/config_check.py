"""Offline container smoke command that validates configuration only."""

from app.core.config import get_settings


def main() -> None:
    """Validate settings without opening DB, polling, or contacting Telegram."""
    get_settings()
    print("Configuration is valid.")


if __name__ == "__main__":
    main()
