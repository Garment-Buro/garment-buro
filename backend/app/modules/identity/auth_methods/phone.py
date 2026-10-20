from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.modules.identity.auth_methods.base import AuthMethodDescriptor
from app.modules.identity.exceptions import AuthMethodUnavailableError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.identity.service import AuthSessionTokens, IdentityService, IssuedOtp


class PhoneOtpAuthMethod:
    """Provider-neutral phone OTP flow, kept disabled until SMS is selected."""

    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled

    @property
    def descriptor(self) -> AuthMethodDescriptor:
        return AuthMethodDescriptor(
            code="phone",
            kind="otp",
            enabled=self.enabled,
            reason=None if self.enabled else "provider_not_configured",
        )

    async def request_code(
        self,
        service: IdentityService,
        session: AsyncSession,
        *,
        phone: str,
        now: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> IssuedOtp:
        self._require_enabled()
        return await service.request_login_phone_otp(
            session,
            phone=phone,
            now=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    async def verify_code(
        self,
        service: IdentityService,
        session: AsyncSession,
        *,
        phone: str,
        code: str,
        now: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthSessionTokens:
        self._require_enabled()
        return await service.verify_login_phone_otp(
            session,
            phone=phone,
            code=code,
            now=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise AuthMethodUnavailableError("Phone authentication provider is not configured")
