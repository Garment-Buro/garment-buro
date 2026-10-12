from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.modules.identity.auth_methods.base import AuthMethodDescriptor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.identity.service import AuthSessionTokens, IdentityService, IssuedOtp


class EmailOtpAuthMethod:
    @property
    def descriptor(self) -> AuthMethodDescriptor:
        return AuthMethodDescriptor(code="email", kind="otp", enabled=True)

    async def request_code(
        self,
        service: IdentityService,
        session: AsyncSession,
        *,
        email: str,
        now: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> IssuedOtp:
        return await service.request_login_otp(
            session,
            email=email,
            now=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    async def verify_code(
        self,
        service: IdentityService,
        session: AsyncSession,
        *,
        email: str,
        code: str,
        now: datetime,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AuthSessionTokens:
        return await service.verify_login_otp(
            session,
            email=email,
            code=code,
            now=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )
