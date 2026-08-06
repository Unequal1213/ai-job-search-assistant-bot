"""Async SQLAlchemy engine, session factory, and connectivity helpers."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

SessionFactory = async_sessionmaker[AsyncSession]


def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine without connecting at import time."""
    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> SessionFactory:
    """Create sessions with explicit transaction boundaries and no auto-commit."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def check_database_connectivity(engine: AsyncEngine) -> None:
    """Run a lightweight connectivity check before polling starts."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
