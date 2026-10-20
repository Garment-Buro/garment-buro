"""ASGI entrypoint. Resources are opened by lifespan; schema changes use Alembic."""

from app.core.config import get_settings
from app.factory import create_app
from app.observability.logging import configure_logging

configure_logging(get_settings())

app = create_app()
