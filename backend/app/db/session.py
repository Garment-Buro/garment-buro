from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.exceptions import ConfigurationError
from app.db import models as database_models  # noqa: F401


def normalize_async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://") or url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


class DatabaseManager:
    """Own the async engine and session factory for one FastAPI application."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = self.settings.database_enabled
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise ConfigurationError("Async database engine has not been started")
        return self._engine

    @property
    def backend_name(self) -> str:
        if not self.enabled or not self.settings.database_url:
            return "legacy"
        normalized_url = normalize_async_database_url(self.settings.database_url)
        return "sqlite" if normalized_url.startswith("sqlite+") else "postgresql"

    async def startup(self) -> None:
        if not self.enabled or self._engine is not None:
            return
        if not self.settings.database_url:
            raise ConfigurationError("DATABASE_URL is not configured")

        database_url = normalize_async_database_url(self.settings.database_url)
        engine_options: dict[str, object] = {
            "echo": self.settings.database_echo,
            "pool_pre_ping": True,
        }
        if not database_url.startswith("sqlite+"):
            engine_options.update(
                {
                    "pool_size": self.settings.database_pool_size,
                    "max_overflow": self.settings.database_max_overflow,
                }
            )

        self._engine = create_async_engine(database_url, **engine_options)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def shutdown(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._session_factory = None

    async def ping(self) -> bool:
        if not self.enabled or self._engine is None:
            return False
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except (OSError, SQLAlchemyError):
            return False

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._session_factory is None:
            raise ConfigurationError("Async database session factory has not been started")
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = getattr(request.app.state, "database", None)
    if not isinstance(database, DatabaseManager) or not database.enabled:
        raise HTTPException(status_code=503, detail="Database is not enabled")

    try:
        async with database.session() as session:
            yield session
    except ConfigurationError as error:
        raise HTTPException(status_code=503, detail="Database is not ready") from error
