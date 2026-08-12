"""Refactored ASGI entrypoint with the legacy API mounted as a compatibility facade."""

from app.factory import create_app
from main import app as legacy_app

app = create_app(legacy_app=legacy_app)
