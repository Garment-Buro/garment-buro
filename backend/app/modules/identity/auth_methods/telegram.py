from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING

from app.modules.identity.auth_methods.base import AuthMethodDescriptor
from app.modules.identity.exceptions import AuthMethodUnavailableError
from app.modules.identity.telegram import TelegramLoginVerifier

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.identity.service import AuthSessionTokens, IdentityService


class TelegramAuthMethod:
    def __init__(
        self,
        verifier: TelegramLoginVerifier | None,
        *,
        disabled_reason: str = "disabled_by_configuration",
    ) -> None:
        self.verifier = verifier
        self.disabled_reason = disabled_reason

    @property
    def descriptor(self) -> AuthMethodDescriptor:
        return AuthMethodDescriptor(
            code="telegram",
            kind="external",
            enabled=self.verifier is not None,
            reason=None if self.verifier is not None else self.disabled_reason,
        )

    def require_verifier(self) -> TelegramLoginVerifier:
        if self.verifier is None:
            raise AuthMethodUnavailableError("Telegram authentication is not configured")
        return self.verifier

    async def authenticate(
        self,
        service: IdentityService,
        session: AsyncSession,
        *,
        payload: Mapping[str, str | int | None],
        now: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthSessionTokens:
        principal = self.require_verifier().verify(payload, now=now)
        return await service.authenticate_external(
            session,
            principal=principal,
            now=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )
