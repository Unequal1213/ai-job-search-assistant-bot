import asyncio

from app.main import run_bot


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
