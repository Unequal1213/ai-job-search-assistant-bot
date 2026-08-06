import asyncio

from app.core.config import Environment, Settings
from app.main import run_application, run_bot


class FakeBot:
    pass


class FakeDispatcher:
    def __init__(self) -> None:
        self.started = False
        self.bot: FakeBot | None = None

    async def start_polling(self, bot: FakeBot) -> None:
        self.started = True
        self.bot = bot


def test_run_bot_without_token_does_not_start_polling(capsys) -> None:
    dispatcher = FakeDispatcher()

    def create_bot(_: str) -> FakeBot:
        raise AssertionError("Bot should not be created without BOT_TOKEN")

    started = asyncio.run(
        run_bot(
            bot_token=None,
            bot_factory=create_bot,
            dispatcher_factory=lambda: dispatcher,
        )
    )

    captured = capsys.readouterr()

    assert started is False
    assert dispatcher.started is False
    assert "BOT_TOKEN is not set" in captured.out


def test_run_bot_with_token_starts_polling_with_mocked_dispatcher() -> None:
    dispatcher = FakeDispatcher()
    fake_bot = FakeBot()

    started = asyncio.run(
        run_bot(
            bot_token="123456:test-token",
            bot_factory=lambda _: fake_bot,
            dispatcher_factory=lambda: dispatcher,
        )
    )

    assert started is True
    assert dispatcher.started is True
    assert dispatcher.bot is fake_bot


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeClosableBot(FakeBot):
    def __init__(self) -> None:
        self.session = FakeSession()


def test_run_bot_closes_session_after_polling_stops() -> None:
    dispatcher = FakeDispatcher()
    bot = FakeClosableBot()

    started = asyncio.run(
        run_bot(
            bot_token="synthetic-token",
            bot_factory=lambda _: bot,
            dispatcher_factory=lambda: dispatcher,
        )
    )

    assert started is True
    assert bot.session.closed is True


def test_application_initializes_and_shuts_down_without_polling(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        bot_token=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'startup.db'}",
        environment=Environment.TEST,
    )

    started = asyncio.run(run_application(settings))

    assert started is False
