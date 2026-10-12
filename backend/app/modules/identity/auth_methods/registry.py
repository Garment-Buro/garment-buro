from __future__ import annotations

from collections.abc import Iterable

from app.modules.identity.auth_methods.base import AuthMethod, AuthMethodDescriptor
from app.modules.identity.exceptions import AuthMethodUnavailableError


class AuthMethodRegistry:
    """Resolve auth methods without coupling the router to concrete providers."""

    def __init__(self, methods: Iterable[AuthMethod]) -> None:
        self._methods = {method.descriptor.code: method for method in methods}
        if len(self._methods) == 0:
            raise ValueError("At least one authentication method is required")

    def descriptors(self) -> tuple[AuthMethodDescriptor, ...]:
        return tuple(method.descriptor for method in self._methods.values())

    def get(self, code: str) -> AuthMethod:
        method = self._methods.get(code)
        if method is None:
            raise AuthMethodUnavailableError(f"Unknown authentication method: {code}")
        return method
