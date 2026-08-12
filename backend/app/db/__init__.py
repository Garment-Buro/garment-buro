"""SQLAlchemy database foundation for refactored modules."""

from typing import Any

from .base import Base

__all__ = ["Base", "DatabaseManager", "get_database_session"]


def __getattr__(name: str) -> Any:
    """Keep the public imports without loading the model graph recursively."""
    if name in {"DatabaseManager", "get_database_session"}:
        from .session import DatabaseManager, get_database_session

        return {
            "DatabaseManager": DatabaseManager,
            "get_database_session": get_database_session,
        }[name]
    raise AttributeError(name)
