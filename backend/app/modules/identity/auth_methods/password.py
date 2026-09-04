from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.modules.identity.auth_methods.base import AuthMethodDescriptor
from app.modules.identity.exceptions import AuthMethodUnavailableError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.identity.service import AuthSessionTokens, IdentityService


class PasswordAuthMethod:
    def __init__(self, *, enabled: bool) -> None:
        self.enabled = enabled

    @property
    def descriptor(self) -> AuthMethodDescriptor:
        return AuthMethodDescriptor(
            code="password",
            kind="password",
            enabled=self.enabled,
            reason=None if self.enabled else "disabled_by_configuration",
        )

    async def authenticate(
        self,
        service: IdentityService,
        session: AsyncSession,
        *,
        identifier: str,
        password: str,
        now: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthSessionTokens:
        if not self.enabled:
            raise AuthMethodUnavailableError("Password authentication is disabled")
        return await service.authenticate_password(
            session,
            identifier=identifier,
            password=password,
            now=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )
