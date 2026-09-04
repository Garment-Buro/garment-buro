from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.exceptions import (
    EmailAlreadyUsedError,
    ExpiredOtpError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidOtpError,
    InvalidPhoneError,
    InvalidSessionError,
    OtpRateLimitError,
    PermissionDeniedError,
    PhoneAlreadyUsedError,
    RefreshTokenReuseError,
)
from app.modules.identity.models import (
    ExternalAuthProvider,
    OtpChallenge,
    OtpMethod,
    OtpPurpose,
    PasswordCredential,
    PermissionCode,
    RefreshSession,
    User,
    UserStatus,
)
from app.modules.identity.passwords import PasswordSecurity
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import (
    OtpSecurity,
    TokenSecurity,
    ensure_utc,
    normalize_email,
    normalize_phone,
)


@dataclass(frozen=True, slots=True)
class IdentityPolicy:
    otp_lifetime: timedelta = timedelta(minutes=10)
    otp_resend_interval: timedelta = timedelta(seconds=60)
    otp_window: timedelta = timedelta(hours=1)
    otp_window_limit: int = 5
    otp_max_attempts: int = 5
    refresh_lifetime: timedelta = timedelta(days=30)
    max_active_sessions: int = 10
    password_max_attempts: int = 5
    password_lockout: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        positive_durations = (
            self.otp_lifetime,
            self.otp_resend_interval,
            self.otp_window,
            self.refresh_lifetime,
            self.password_lockout,
        )
        if any(duration <= timedelta(0) for duration in positive_durations):
            raise ValueError("Identity policy durations must be positive")
        if not 1 <= self.otp_max_attempts <= 10:
            raise ValueError("OTP max attempts must be between 1 and 10")
        if self.otp_window_limit <= 0 or self.max_active_sessions <= 0:
            raise ValueError("Identity policy limits must be positive")
        if not 1 <= self.password_max_attempts <= 20:
            raise ValueError("Password max attempts must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class IssuedOtp:
    challenge_id: int
    user_id: int
    target_email: str
    code: str
    expires_at: datetime
    invalidated_challenge_ids: tuple[int, ...] = ()

    @property
    def target(self) -> str:
        return self.target_email


@dataclass(frozen=True, slots=True)
class AuthSessionTokens:
    user: User
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    session_id: str
    verified_challenge_id: int | None = None


@dataclass(frozen=True, slots=True)
class IdentityAccessSnapshot:
    roles: tuple[str, ...]
    permissions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerifiedEmailChange:
    user: User
    challenge_id: int


@dataclass(frozen=True, slots=True)
class ProfileChanges:
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    height_cm: Decimal | None = None
    weight_kg: Decimal | None = None
    provided_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        allowed = {
            "first_name",
            "last_name",
            "gender",
            "birth_date",
            "phone",
            "height_cm",
            "weight_kg",
        }
        if not self.provided_fields <= allowed:
            raise ValueError("Unsupported profile fields")


@dataclass(frozen=True, slots=True)
class ExternalAuthPrincipal:
    provider: str
    subject: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class IdentityService:
    def __init__(
        self,
        otp_security: OtpSecurity,
        token_security: TokenSecurity,
        *,
        repository: IdentityRepository | None = None,
        policy: IdentityPolicy | None = None,
        password_security: PasswordSecurity | None = None,
    ) -> None:
        self.otp_security = otp_security
        self.token_security = token_security
        self.repository = repository or IdentityRepository()
        self.policy = policy or IdentityPolicy()
        self.password_security = password_security or PasswordSecurity()

    async def authenticate_password(
        self,
        session: AsyncSession,
        *,
        identifier: str,
        password: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSessionTokens:
        now = ensure_utc(now)
        user: User | None
        if "@" in identifier:
            try:
                _, normalized = normalize_email(identifier)
            except InvalidEmailError:
                normalized = ""
            user = await self.repository.get_user_by_email(session, normalized, for_update=True)
        else:
            try:
                _, normalized = normalize_phone(identifier)
            except InvalidPhoneError:
                normalized = ""
            user = await self.repository.get_user_by_phone(session, normalized, for_update=True)
            if user is not None and user.phone_verified_at is None:
                user = None

        if user is None or user.status != UserStatus.ACTIVE.value:
            self.password_security.verify_missing_user(password)
            raise InvalidCredentialsError("Invalid identifier or password")
        credential = await self.repository.get_password_credential(
            session,
            user_id=user.id,
            for_update=True,
        )
        if credential is None:
            self.password_security.verify_missing_user(password)
            raise InvalidCredentialsError("Invalid identifier or password")
        if credential.locked_until is not None and ensure_utc(credential.locked_until) > now:
            self.password_security.verify_missing_user(password)
            raise InvalidCredentialsError("Invalid identifier or password")

        ip_digest = self.otp_security.digest_client_value(client_ip)
        if not self.password_security.verify(credential.password_hash, password):
            credential.failed_attempts += 1
            if credential.failed_attempts >= self.policy.password_max_attempts:
                credential.failed_attempts = 0
                credential.locked_until = now + self.policy.password_lockout
            await self.repository.add_audit_event(
                session,
                event_type="auth.password_failed",
                subject_user_id=user.id,
                ip_digest=ip_digest,
                user_agent=user_agent,
            )
            await session.commit()
            raise InvalidCredentialsError("Invalid identifier or password")

        credential.failed_attempts = 0
        credential.locked_until = None
        credential.last_used_at = now
        if self.password_security.needs_rehash(credential.password_hash):
            credential.password_hash = self.password_security.hash(password)
        tokens, _ = await self._new_session(
            session,
            user=user,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await self.repository.add_audit_event(
            session,
            event_type="auth.password_succeeded",
            actor_user_id=user.id,
            subject_user_id=user.id,
            session_id=tokens.session_id,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await session.flush()
        return tokens

    async def set_password(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        new_password: str,
        current_password: str | None,
        now: datetime,
    ) -> None:
        if not 10 <= len(new_password) <= 128:
            raise ValueError("Password must contain between 10 and 128 characters")
        user = await self.repository.get_user(session, user_id, for_update=True)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("User is not active")
        credential = await self.repository.get_password_credential(
            session,
            user_id=user.id,
            for_update=True,
        )
        if credential is not None:
            if current_password is None or not self.password_security.verify(
                credential.password_hash,
                current_password,
            ):
                raise InvalidCredentialsError("Current password is invalid")
            credential.password_hash = self.password_security.hash(new_password)
            credential.password_changed_at = ensure_utc(now)
            credential.failed_attempts = 0
            credential.locked_until = None
        else:
            session.add(
                PasswordCredential(
                    user_id=user.id,
                    password_hash=self.password_security.hash(new_password),
                    password_changed_at=ensure_utc(now),
                )
            )
        await self.repository.add_audit_event(
            session,
            event_type="auth.password_changed",
            actor_user_id=user.id,
            subject_user_id=user.id,
        )
        await session.flush()

    async def authenticate_external(
        self,
        session: AsyncSession,
        *,
        principal: ExternalAuthPrincipal,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSessionTokens:
        now = ensure_utc(now)
        if principal.provider not in {provider.value for provider in ExternalAuthProvider}:
            raise ValueError("Unsupported external authentication provider")
        if not principal.subject or len(principal.subject) > 255:
            raise ValueError("Invalid external authentication subject")
        user = await self.repository.get_or_create_external_customer(
            session,
            provider=principal.provider,
            subject=principal.subject,
            first_name=principal.first_name,
            last_name=principal.last_name,
            username=principal.username,
            verified_at=now,
        )
        if user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("User is not active")
        user.first_name = user.first_name or principal.first_name
        user.last_name = user.last_name or principal.last_name
        user.username = principal.username or user.username
        ip_digest = self.otp_security.digest_client_value(client_ip)
        tokens, _ = await self._new_session(
            session,
            user=user,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await self.repository.add_audit_event(
            session,
            event_type=f"auth.{principal.provider}.succeeded",
            actor_user_id=user.id,
            subject_user_id=user.id,
            session_id=tokens.session_id,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await session.flush()
        return tokens

    async def request_login_otp(
        self,
        session: AsyncSession,
        *,
        email: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedOtp:
        now = ensure_utc(now)
        display_email, normalized_email = normalize_email(email)
        ip_digest = self.otp_security.digest_client_value(client_ip)
        await self._enforce_otp_request_limits(
            session,
            target_email_normalized=normalized_email,
            purpose=OtpPurpose.LOGIN,
            ip_digest=ip_digest,
            now=now,
        )

        user = await self.repository.get_or_create_customer(
            session,
            email=display_email,
            email_normalized=normalized_email,
        )
        await self._enforce_otp_request_limits(
            session,
            target_email_normalized=normalized_email,
            purpose=OtpPurpose.LOGIN,
            ip_digest=ip_digest,
            now=now,
        )
        if user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("User is not active")

        code = self.otp_security.generate_code()
        salt = self.otp_security.generate_salt()
        expires_at = now + self.policy.otp_lifetime
        challenge = OtpChallenge(
            user_id=user.id,
            purpose=OtpPurpose.LOGIN.value,
            method=OtpMethod.EMAIL.value,
            target_value=display_email,
            target_normalized=normalized_email,
            target_email=display_email,
            target_email_normalized=normalized_email,
            code_digest=self.otp_security.digest(
                code=code,
                salt=salt,
                purpose=OtpPurpose.LOGIN,
                target_email_normalized=normalized_email,
            ),
            code_salt=salt,
            expires_at=expires_at,
            max_attempts=self.policy.otp_max_attempts,
            active_key=self.repository.active_challenge_key(user.id, OtpPurpose.LOGIN),
            requested_ip_digest=ip_digest,
        )
        invalidated_challenge_ids = await self.repository.replace_active_challenge(
            session,
            challenge,
            invalidated_at=now,
        )
        await self.repository.add_audit_event(
            session,
            event_type="auth.otp_requested",
            subject_user_id=user.id,
            ip_digest=ip_digest,
            user_agent=user_agent,
            details={"purpose": OtpPurpose.LOGIN.value},
        )
        await session.flush()
        return IssuedOtp(
            challenge_id=challenge.id,
            user_id=user.id,
            target_email=display_email,
            code=code,
            expires_at=expires_at,
            invalidated_challenge_ids=tuple(invalidated_challenge_ids),
        )

    async def request_login_phone_otp(
        self,
        session: AsyncSession,
        *,
        phone: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedOtp:
        now = ensure_utc(now)
        display_phone, normalized_phone = normalize_phone(phone)
        ip_digest = self.otp_security.digest_client_value(client_ip)
        await self._enforce_otp_request_limits(
            session,
            target_email_normalized=normalized_phone,
            purpose=OtpPurpose.LOGIN,
            method=OtpMethod.PHONE,
            ip_digest=ip_digest,
            now=now,
        )
        user = await self.repository.get_or_create_phone_customer(
            session,
            phone=display_phone,
            phone_normalized=normalized_phone,
        )
        await self._enforce_otp_request_limits(
            session,
            target_email_normalized=normalized_phone,
            purpose=OtpPurpose.LOGIN,
            method=OtpMethod.PHONE,
            ip_digest=ip_digest,
            now=now,
        )
        if user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("User is not active")

        code = self.otp_security.generate_code()
        salt = self.otp_security.generate_salt()
        expires_at = now + self.policy.otp_lifetime
        challenge = OtpChallenge(
            user_id=user.id,
            purpose=OtpPurpose.LOGIN.value,
            method=OtpMethod.PHONE.value,
            target_value=display_phone,
            target_normalized=normalized_phone,
            target_email=display_phone,
            target_email_normalized=normalized_phone,
            code_digest=self.otp_security.digest(
                code=code,
                salt=salt,
                purpose=OtpPurpose.LOGIN,
                target_email_normalized=normalized_phone,
                method=OtpMethod.PHONE,
            ),
            code_salt=salt,
            expires_at=expires_at,
            max_attempts=self.policy.otp_max_attempts,
            active_key=self.repository.active_challenge_key(
                user.id,
                OtpPurpose.LOGIN,
                method=OtpMethod.PHONE,
            ),
            requested_ip_digest=ip_digest,
        )
        invalidated_challenge_ids = await self.repository.replace_active_challenge(
            session,
            challenge,
            invalidated_at=now,
        )
        await self.repository.add_audit_event(
            session,
            event_type="auth.phone.otp_requested",
            subject_user_id=user.id,
            ip_digest=ip_digest,
            user_agent=user_agent,
            details={"purpose": OtpPurpose.LOGIN.value, "method": OtpMethod.PHONE.value},
        )
        await session.flush()
        return IssuedOtp(
            challenge_id=challenge.id,
            user_id=user.id,
            target_email=display_phone,
            code=code,
            expires_at=expires_at,
            invalidated_challenge_ids=tuple(invalidated_challenge_ids),
        )

    async def request_email_change_otp(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        email: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedOtp:
        now = ensure_utc(now)
        display_email, normalized_email = normalize_email(email)
        user = await self.repository.get_user(session, user_id, for_update=True)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("User is not active")
        existing = await self.repository.get_user_by_email(session, normalized_email)
        if existing is not None and existing.id != user.id:
            raise EmailAlreadyUsedError("Email is already used")

        ip_digest = self.otp_security.digest_client_value(client_ip)
        await self._enforce_otp_request_limits(
            session,
            target_email_normalized=normalized_email,
            purpose=OtpPurpose.EMAIL_CHANGE,
            ip_digest=ip_digest,
            now=now,
        )
        code = self.otp_security.generate_code()
        salt = self.otp_security.generate_salt()
        expires_at = now + self.policy.otp_lifetime
        challenge = OtpChallenge(
            user_id=user.id,
            purpose=OtpPurpose.EMAIL_CHANGE.value,
            method=OtpMethod.EMAIL.value,
            target_value=display_email,
            target_normalized=normalized_email,
            target_email=display_email,
            target_email_normalized=normalized_email,
            code_digest=self.otp_security.digest(
                code=code,
                salt=salt,
                purpose=OtpPurpose.EMAIL_CHANGE,
                target_email_normalized=normalized_email,
            ),
            code_salt=salt,
            expires_at=expires_at,
            max_attempts=self.policy.otp_max_attempts,
            active_key=self.repository.active_challenge_key(
                user.id,
                OtpPurpose.EMAIL_CHANGE,
            ),
            requested_ip_digest=ip_digest,
        )
        invalidated_challenge_ids = await self.repository.replace_active_challenge(
            session,
            challenge,
            invalidated_at=now,
        )
        await self.repository.add_audit_event(
            session,
            event_type="profile.email.otp_requested",
            actor_user_id=user.id,
            subject_user_id=user.id,
            ip_digest=ip_digest,
            user_agent=user_agent,
            details={"purpose": OtpPurpose.EMAIL_CHANGE.value},
        )
        await session.flush()
        return IssuedOtp(
            challenge_id=challenge.id,
            user_id=user.id,
            target_email=display_email,
            code=code,
            expires_at=expires_at,
            invalidated_challenge_ids=tuple(invalidated_challenge_ids),
        )

    async def verify_login_otp(
        self,
        session: AsyncSession,
        *,
        email: str,
        code: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSessionTokens:
        now = ensure_utc(now)
        _, normalized_email = normalize_email(email)
        ip_digest = self.otp_security.digest_client_value(client_ip)
        user = await self.repository.get_user_by_email(
            session,
            normalized_email,
            for_update=True,
        )
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InvalidOtpError("Invalid code")
        challenge = await self._verify_challenge(
            session,
            user=user,
            purpose=OtpPurpose.LOGIN,
            target_email_normalized=normalized_email,
            code=code,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
            event_prefix="auth",
        )

        challenge.consumed_at = now
        challenge.active_key = None
        user.email_verified_at = user.email_verified_at or now
        tokens, _ = await self._new_session(
            session,
            user=user,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
            verified_challenge_id=challenge.id,
        )
        await self.repository.add_audit_event(
            session,
            event_type="auth.login_succeeded",
            actor_user_id=user.id,
            subject_user_id=user.id,
            session_id=tokens.session_id,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await session.flush()
        return tokens

    async def verify_login_phone_otp(
        self,
        session: AsyncSession,
        *,
        phone: str,
        code: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSessionTokens:
        now = ensure_utc(now)
        _, normalized_phone = normalize_phone(phone)
        ip_digest = self.otp_security.digest_client_value(client_ip)
        user = await self.repository.get_user_by_phone(
            session,
            normalized_phone,
            for_update=True,
        )
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InvalidOtpError("Invalid code")
        challenge = await self._verify_challenge(
            session,
            user=user,
            purpose=OtpPurpose.LOGIN,
            method=OtpMethod.PHONE,
            target_email_normalized=normalized_phone,
            code=code,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
            event_prefix="auth.phone",
        )
        challenge.consumed_at = now
        challenge.active_key = None
        user.phone_verified_at = user.phone_verified_at or now
        tokens, _ = await self._new_session(
            session,
            user=user,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
            verified_challenge_id=challenge.id,
        )
        await self.repository.add_audit_event(
            session,
            event_type="auth.phone.login_succeeded",
            actor_user_id=user.id,
            subject_user_id=user.id,
            session_id=tokens.session_id,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await session.flush()
        return tokens

    async def verify_email_change_otp(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        email: str,
        code: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> VerifiedEmailChange:
        now = ensure_utc(now)
        display_email, normalized_email = normalize_email(email)
        ip_digest = self.otp_security.digest_client_value(client_ip)
        user = await self.repository.get_user(session, user_id, for_update=True)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InvalidOtpError("Invalid code")
        challenge = await self._verify_challenge(
            session,
            user=user,
            purpose=OtpPurpose.EMAIL_CHANGE,
            target_email_normalized=normalized_email,
            code=code,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
            event_prefix="profile.email",
        )
        existing = await self.repository.get_user_by_email(session, normalized_email)
        if existing is not None and existing.id != user.id:
            raise EmailAlreadyUsedError("Email is already used")

        try:
            async with session.begin_nested():
                user.email = display_email
                user.email_normalized = normalized_email
                user.email_verified_at = now
                await session.flush()
        except IntegrityError as error:
            raise EmailAlreadyUsedError("Email is already used") from error

        challenge.consumed_at = now
        challenge.active_key = None
        await self.repository.add_audit_event(
            session,
            event_type="profile.email_changed",
            actor_user_id=user.id,
            subject_user_id=user.id,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await session.flush()
        return VerifiedEmailChange(user=user, challenge_id=challenge.id)

    async def resolve_access_token(
        self,
        session: AsyncSession,
        *,
        access_token: str,
        now: datetime,
        allow_legacy: bool,
    ) -> User:
        now = ensure_utc(now)
        try:
            claims = self.token_security.decode_access_token(access_token)
        except InvalidSessionError:
            if not allow_legacy:
                raise
            legacy_claims = self.token_security.decode_legacy_access_token(access_token)
            user = await self.repository.get_user(session, legacy_claims.user_id)
        else:
            user = await self.repository.get_active_user_for_session(
                session,
                user_id=claims.user_id,
                session_id=claims.session_id,
                now=now,
            )
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InvalidSessionError("Invalid access session")
        return user

    async def migrate_legacy_access_token(
        self,
        session: AsyncSession,
        *,
        access_token: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSessionTokens:
        now = ensure_utc(now)
        claims = self.token_security.decode_legacy_access_token(access_token)
        user = await self.repository.get_user(
            session,
            claims.user_id,
            for_update=True,
        )
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InvalidSessionError("Invalid legacy access session")
        ip_digest = self.otp_security.digest_client_value(client_ip)
        tokens, _ = await self._new_session(
            session,
            user=user,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await self.repository.add_audit_event(
            session,
            event_type="auth.legacy_session_migrated",
            actor_user_id=user.id,
            subject_user_id=user.id,
            session_id=tokens.session_id,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await session.flush()
        return tokens

    async def update_profile(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        changes: ProfileChanges,
        now: datetime,
    ) -> User:
        user = await self.repository.get_user(session, user_id, for_update=True)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("User is not active")
        try:
            async with session.begin_nested():
                for field_name in changes.provided_fields:
                    value = getattr(changes, field_name)
                    if field_name == "phone":
                        if value is None:
                            user.phone = None
                            user.phone_normalized = None
                            user.phone_verified_at = None
                        else:
                            display_phone, normalized_phone = normalize_phone(value)
                            user.phone = display_phone
                            user.phone_normalized = normalized_phone
                            user.phone_verified_at = None
                        continue
                    setattr(user, field_name, value)
                user.updated_at = ensure_utc(now)
                await session.flush()
        except IntegrityError as error:
            raise PhoneAlreadyUsedError("Phone is already used") from error
        await self.repository.add_audit_event(
            session,
            event_type="profile.updated",
            actor_user_id=user.id,
            subject_user_id=user.id,
            details={"fields": sorted(changes.provided_fields)},
        )
        await session.flush()
        return user

    async def delete_profile(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        now: datetime,
    ) -> None:
        now = ensure_utc(now)
        user = await self.repository.get_user(session, user_id, for_update=True)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("User is not active")
        await self.repository.revoke_user_sessions(
            session,
            user_id=user.id,
            revoked_at=now,
        )
        await self.repository.invalidate_user_challenges(
            session,
            user_id=user.id,
            invalidated_at=now,
        )
        await self.repository.delete_user_auth_credentials(session, user_id=user.id)
        user.email = None
        user.email_normalized = None
        user.telegram_id = None
        user.phone_normalized = None
        user.primary_auth_provider = None
        user.primary_auth_subject = None
        user.first_name = None
        user.last_name = None
        user.username = None
        user.phone = None
        user.gender = None
        user.birth_date = None
        user.height_cm = None
        user.weight_kg = None
        user.email_verified_at = None
        user.phone_verified_at = None
        user.status = UserStatus.DELETED.value
        user.updated_at = now
        await self.repository.add_audit_event(
            session,
            event_type="profile.deleted",
            actor_user_id=user.id,
            subject_user_id=user.id,
        )
        await session.flush()

    async def rotate_refresh_token(
        self,
        session: AsyncSession,
        *,
        refresh_token: str,
        now: datetime,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSessionTokens:
        now = ensure_utc(now)
        digest = self.token_security.digest_refresh_token(refresh_token)
        current = await self.repository.get_refresh_session(session, digest)
        if current is None:
            raise InvalidSessionError("Invalid refresh token")
        ip_digest = self.otp_security.digest_client_value(client_ip)
        if current.revoked_at is not None:
            if current.replaced_by_id is not None:
                await self.repository.revoke_session_family(
                    session,
                    family_id=current.family_id,
                    revoked_at=now,
                )
                await self.repository.add_audit_event(
                    session,
                    event_type="auth.refresh_reuse_detected",
                    subject_user_id=current.user_id,
                    session_id=current.session_id,
                    ip_digest=ip_digest,
                    user_agent=user_agent,
                )
                await session.commit()
                raise RefreshTokenReuseError("Refresh token reuse detected")
            raise InvalidSessionError("Refresh session is revoked")
        if ensure_utc(current.expires_at) <= now:
            current.revoked_at = now
            await session.commit()
            raise InvalidSessionError("Refresh session expired")
        if current.user.status != UserStatus.ACTIVE.value:
            current.revoked_at = now
            await session.commit()
            raise InactiveUserError("User is not active")

        replacement, replacement_model = await self._new_session(
            session,
            user=current.user,
            now=now,
            ip_digest=ip_digest,
            user_agent=user_agent,
            family_id=current.family_id,
            generation=current.generation + 1,
            enforce_limit=False,
        )
        current.revoked_at = now
        current.last_seen_at = now
        current.replaced_by_id = replacement_model.id
        await self.repository.add_audit_event(
            session,
            event_type="auth.refresh_rotated",
            actor_user_id=current.user_id,
            subject_user_id=current.user_id,
            session_id=replacement.session_id,
            ip_digest=ip_digest,
            user_agent=user_agent,
        )
        await session.flush()
        return replacement

    async def revoke_refresh_token(
        self,
        session: AsyncSession,
        *,
        refresh_token: str,
        now: datetime,
    ) -> None:
        digest = self.token_security.digest_refresh_token(refresh_token)
        refresh_session = await self.repository.get_refresh_session(session, digest)
        if refresh_session is None:
            return
        refresh_session.revoked_at = refresh_session.revoked_at or ensure_utc(now)
        await self.repository.add_audit_event(
            session,
            event_type="auth.logout",
            actor_user_id=refresh_session.user_id,
            subject_user_id=refresh_session.user_id,
            session_id=refresh_session.session_id,
        )
        await session.flush()

    async def require_permission(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        permission: PermissionCode,
    ) -> None:
        if not await self.repository.user_has_permission(
            session,
            user_id=user_id,
            permission=permission,
        ):
            raise PermissionDeniedError(f"Missing permission: {permission.value}")

    async def get_access_snapshot(
        self,
        session: AsyncSession,
        *,
        user_id: int,
    ) -> IdentityAccessSnapshot:
        roles, permissions = await self.repository.get_user_access(
            session,
            user_id=user_id,
        )
        return IdentityAccessSnapshot(roles=roles, permissions=permissions)

    async def _verify_challenge(
        self,
        session: AsyncSession,
        *,
        user: User,
        purpose: OtpPurpose,
        method: OtpMethod = OtpMethod.EMAIL,
        target_email_normalized: str,
        code: str,
        now: datetime,
        ip_digest: str | None,
        user_agent: str | None,
        event_prefix: str,
    ) -> OtpChallenge:
        challenge = await self.repository.get_active_challenge(
            session,
            user_id=user.id,
            purpose=purpose,
            method=method,
        )
        if (
            challenge is None
            or (challenge.target_normalized or challenge.target_email_normalized)
            != target_email_normalized
        ):
            raise InvalidOtpError("Invalid code")
        if ensure_utc(challenge.expires_at) <= now:
            challenge.invalidated_at = now
            challenge.active_key = None
            await self.repository.add_audit_event(
                session,
                event_type=f"{event_prefix}.otp_expired",
                subject_user_id=user.id,
                ip_digest=ip_digest,
                user_agent=user_agent,
            )
            await session.commit()
            raise ExpiredOtpError("Code expired")

        verified = self.otp_security.verify(
            code=code,
            salt=challenge.code_salt,
            purpose=purpose,
            target_email_normalized=challenge.target_email_normalized,
            expected_digest=challenge.code_digest,
            method=method,
        )
        if not verified:
            challenge.attempts_count += 1
            if challenge.attempts_count >= challenge.max_attempts:
                challenge.invalidated_at = now
                challenge.active_key = None
            await self.repository.add_audit_event(
                session,
                event_type=f"{event_prefix}.otp_failed",
                subject_user_id=user.id,
                ip_digest=ip_digest,
                user_agent=user_agent,
                details={"attempts": challenge.attempts_count},
            )
            await session.commit()
            raise InvalidOtpError("Invalid code")
        return challenge

    async def _new_session(
        self,
        session: AsyncSession,
        *,
        user: User,
        now: datetime,
        ip_digest: str | None,
        user_agent: str | None,
        family_id: str | None = None,
        generation: int = 0,
        enforce_limit: bool = True,
        verified_challenge_id: int | None = None,
    ) -> tuple[AuthSessionTokens, RefreshSession]:
        if enforce_limit:
            active_count = await self.repository.active_session_count(
                session,
                user_id=user.id,
                now=now,
            )
            overflow = active_count - self.policy.max_active_sessions + 1
            await self.repository.revoke_oldest_active_sessions(
                session,
                user_id=user.id,
                now=now,
                count=overflow,
            )

        session_id = str(uuid4())
        family_id = family_id or str(uuid4())
        refresh_token = self.token_security.create_refresh_token()
        refresh_expires_at = now + self.policy.refresh_lifetime
        refresh_session = RefreshSession(
            session_id=session_id,
            family_id=family_id,
            user_id=user.id,
            token_digest=self.token_security.digest_refresh_token(refresh_token),
            generation=generation,
            expires_at=refresh_expires_at,
            ip_digest=ip_digest,
            user_agent=(user_agent or "")[:512] or None,
        )
        await self.repository.create_refresh_session(session, refresh_session)
        access_token, access_expires_at = self.token_security.create_access_token(
            user_id=user.id,
            session_id=session_id,
            now=now,
        )
        return (
            AuthSessionTokens(
                user=user,
                access_token=access_token,
                access_expires_at=access_expires_at,
                refresh_token=refresh_token,
                refresh_expires_at=refresh_expires_at,
                session_id=session_id,
                verified_challenge_id=verified_challenge_id,
            ),
            refresh_session,
        )

    async def _enforce_otp_request_limits(
        self,
        session: AsyncSession,
        *,
        target_email_normalized: str,
        purpose: OtpPurpose,
        method: OtpMethod = OtpMethod.EMAIL,
        ip_digest: str | None,
        now: datetime,
    ) -> None:
        latest = await self.repository.latest_challenge(
            session,
            target_email_normalized=target_email_normalized,
            purpose=purpose,
            method=method,
        )
        if latest is not None:
            elapsed = now - ensure_utc(latest.created_at)
            if elapsed < self.policy.otp_resend_interval:
                retry_after = int((self.policy.otp_resend_interval - elapsed).total_seconds())
                raise OtpRateLimitError(retry_after)
        recent_count = await self.repository.recent_challenge_count(
            session,
            target_email_normalized=target_email_normalized,
            requested_ip_digest=ip_digest,
            since=now - self.policy.otp_window,
            method=method,
        )
        if recent_count >= self.policy.otp_window_limit:
            raise OtpRateLimitError(int(self.policy.otp_window.total_seconds()))
