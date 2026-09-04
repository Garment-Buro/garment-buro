from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    Security,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppEnvironment, Settings
from app.db.session import get_database_session
from app.modules.identity.auth_methods.email import EmailOtpAuthMethod
from app.modules.identity.auth_methods.password import PasswordAuthMethod
from app.modules.identity.auth_methods.phone import PhoneOtpAuthMethod
from app.modules.identity.auth_methods.registry import AuthMethodRegistry
from app.modules.identity.auth_methods.telegram import TelegramAuthMethod
from app.modules.identity.exceptions import (
    AuthMethodUnavailableError,
    EmailAlreadyUsedError,
    ExpiredOtpError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidExternalAuthPayloadError,
    InvalidOtpError,
    InvalidPhoneError,
    InvalidSessionError,
    OtpRateLimitError,
    PermissionDeniedError,
    PhoneAlreadyUsedError,
    RefreshTokenReuseError,
)
from app.modules.identity.models import PermissionCode, User
from app.modules.identity.schemas import (
    AuthAccessResponse,
    AuthEmailRequest,
    AuthMethodResponse,
    AuthMethodsResponse,
    AuthPhoneRequest,
    AuthPhoneVerifyRequest,
    AuthSessionResponse,
    AuthUserResponse,
    AuthVerifyRequest,
    DeletedResponse,
    EmailCodeRequestResponse,
    LoggedOutResponse,
    PasswordLoginRequest,
    PasswordUpdatedResponse,
    ProfileUpdateRequest,
    SetPasswordRequest,
    TelegramLoginRequest,
)
from app.modules.identity.security import ensure_utc
from app.modules.identity.service import (
    AuthSessionTokens,
    IdentityService,
    ProfileChanges,
)
from app.modules.notifications.models import NotificationChannel
from app.modules.notifications.service import NotificationOutboxService
from app.modules.orders.schemas import LegacyOrderResponse
from app.modules.orders.service import OwnedOrderService

router = APIRouter(prefix="/api/auth", tags=["identity"])
bearer = HTTPBearer(auto_error=False)


def get_identity_service(request: Request) -> IdentityService:
    return request.app.state.identity_service


def get_auth_method_registry(request: Request) -> AuthMethodRegistry:
    return request.app.state.auth_method_registry


def get_notification_outbox_service(request: Request) -> NotificationOutboxService:
    return request.app.state.notification_outbox_service


def get_order_bridge_service(request: Request) -> OwnedOrderService:
    return request.app.state.order_bridge_service


async def get_optional_current_identity_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer),
    ],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[IdentityService, Depends(get_identity_service)],
) -> User | None:
    if credentials is None:
        if request.headers.get("authorization") is not None:
            raise _unauthorized()
        return None
    if credentials.scheme.casefold() != "bearer":
        raise _unauthorized()
    now = _utc_now()
    grace_until = request.app.state.settings.identity_legacy_token_grace_until
    allow_legacy = grace_until is not None and now <= ensure_utc(grace_until)
    try:
        return await service.resolve_access_token(
            session,
            access_token=credentials.credentials,
            now=now,
            allow_legacy=allow_legacy,
        )
    except InvalidSessionError as error:
        raise _unauthorized() from error


async def get_current_identity_user(
    user: Annotated[User | None, Depends(get_optional_current_identity_user)],
) -> User:
    if user is None:
        raise _unauthorized()
    return user


@router.get("/methods", response_model=AuthMethodsResponse)
async def get_auth_methods(
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> AuthMethodsResponse:
    return AuthMethodsResponse(
        methods=[
            AuthMethodResponse(
                code=item.code,
                kind=item.kind,
                enabled=item.enabled,
                reason=item.reason,
            )
            for item in methods.descriptors()
        ]
    )


@router.post("/phone/request", response_model=EmailCodeRequestResponse)
async def request_login_phone_code(
    payload: AuthPhoneRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    notifications: Annotated[
        NotificationOutboxService,
        Depends(get_notification_outbox_service),
    ],
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> EmailCodeRequestResponse:
    method = methods.get("phone")
    if not isinstance(method, PhoneOtpAuthMethod):
        raise HTTPException(status_code=503, detail="Phone authentication is unavailable")
    now = _utc_now()
    try:
        issued = await method.request_code(
            identity,
            session,
            phone=payload.phone,
            now=now,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthMethodUnavailableError as error:
        raise HTTPException(status_code=503, detail="Phone provider is not configured") from error
    except OtpRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many code requests",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    except InvalidPhoneError as error:
        raise HTTPException(status_code=400, detail="Invalid phone") from error
    except InactiveUserError:
        return EmailCodeRequestResponse()

    await notifications.cancel_auth_otp(
        session,
        challenge_ids=issued.invalidated_challenge_ids,
        now=now,
        reason="challenge_replaced",
    )
    await notifications.enqueue_auth_otp(
        session,
        recipient=issued.target,
        code=issued.code,
        purpose="login",
        expires_minutes=int(identity.policy.otp_lifetime.total_seconds() // 60),
        deduplication_key=f"otp:challenge:{issued.challenge_id}",
        now=now,
        discard_after=issued.expires_at,
        channel=NotificationChannel.PHONE,
    )
    await session.commit()
    return EmailCodeRequestResponse()


@router.post("/phone/verify", response_model=AuthSessionResponse)
async def verify_login_phone_code(
    payload: AuthPhoneVerifyRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    notifications: Annotated[
        NotificationOutboxService,
        Depends(get_notification_outbox_service),
    ],
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> AuthSessionResponse:
    method = methods.get("phone")
    if not isinstance(method, PhoneOtpAuthMethod):
        raise HTTPException(status_code=503, detail="Phone authentication is unavailable")
    try:
        tokens = await method.verify_code(
            identity,
            session,
            phone=payload.phone,
            code=payload.code,
            now=_utc_now(),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthMethodUnavailableError as error:
        raise HTTPException(status_code=503, detail="Phone provider is not configured") from error
    except (ExpiredOtpError, InactiveUserError, InvalidOtpError, InvalidPhoneError) as error:
        raise HTTPException(status_code=400, detail="Invalid code") from error
    if tokens.verified_challenge_id is not None:
        await notifications.cancel_auth_otp(
            session,
            challenge_ids=[tokens.verified_challenge_id],
            now=_utc_now(),
            reason="challenge_consumed",
        )
    await session.commit()
    _set_refresh_cookie(response, request.app.state.settings, tokens)
    return _session_response(tokens)


@router.post("/password/login", response_model=AuthSessionResponse)
async def login_with_password(
    payload: PasswordLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> AuthSessionResponse:
    method = methods.get("password")
    if not isinstance(method, PasswordAuthMethod):
        raise HTTPException(status_code=503, detail="Password authentication is unavailable")
    try:
        tokens = await method.authenticate(
            identity,
            session,
            identifier=payload.identifier,
            password=payload.password.get_secret_value(),
            now=_utc_now(),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthMethodUnavailableError as error:
        raise HTTPException(
            status_code=503, detail="Password authentication is disabled"
        ) from error
    except InvalidCredentialsError as error:
        raise _unauthorized() from error
    await session.commit()
    _set_refresh_cookie(response, request.app.state.settings, tokens)
    return _session_response(tokens)


@router.put("/password", response_model=PasswordUpdatedResponse)
async def update_password(
    payload: SetPasswordRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> PasswordUpdatedResponse:
    if not methods.get("password").descriptor.enabled:
        raise HTTPException(status_code=503, detail="Password authentication is disabled")
    try:
        await identity.set_password(
            session,
            user_id=user.id,
            new_password=payload.new_password.get_secret_value(),
            current_password=(
                payload.current_password.get_secret_value()
                if payload.current_password is not None
                else None
            ),
            now=_utc_now(),
        )
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=400, detail="Current password is invalid") from error
    await session.commit()
    return PasswordUpdatedResponse()


@router.post("/telegram", response_model=AuthSessionResponse)
async def login_with_telegram(
    payload: TelegramLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> AuthSessionResponse:
    method = methods.get("telegram")
    if not isinstance(method, TelegramAuthMethod):
        raise HTTPException(status_code=503, detail="Telegram authentication is unavailable")
    try:
        tokens = await method.authenticate(
            identity,
            session,
            payload=payload.model_dump(),
            now=_utc_now(),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthMethodUnavailableError as error:
        raise HTTPException(
            status_code=503, detail="Telegram authentication is disabled"
        ) from error
    except (InvalidExternalAuthPayloadError, InactiveUserError) as error:
        raise HTTPException(status_code=400, detail="Invalid Telegram login payload") from error
    await session.commit()
    _set_refresh_cookie(response, request.app.state.settings, tokens)
    return _session_response(tokens)


@router.post("/email/request", response_model=EmailCodeRequestResponse)
async def request_login_email_code(
    payload: AuthEmailRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    notifications: Annotated[
        NotificationOutboxService,
        Depends(get_notification_outbox_service),
    ],
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> EmailCodeRequestResponse:
    now = _utc_now()
    method = methods.get("email")
    if not isinstance(method, EmailOtpAuthMethod):
        raise HTTPException(status_code=503, detail="Email authentication is unavailable")
    try:
        issued = await method.request_code(
            identity,
            session,
            email=payload.email,
            now=now,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except OtpRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many code requests",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    except InvalidEmailError as error:
        raise HTTPException(status_code=400, detail="Invalid email") from error
    except InactiveUserError:
        return EmailCodeRequestResponse()

    await notifications.cancel_auth_otp(
        session,
        challenge_ids=issued.invalidated_challenge_ids,
        now=now,
        reason="challenge_replaced",
    )
    await notifications.enqueue_auth_otp(
        session,
        recipient=issued.target_email,
        code=issued.code,
        purpose="login",
        expires_minutes=int(identity.policy.otp_lifetime.total_seconds() // 60),
        deduplication_key=f"otp:challenge:{issued.challenge_id}",
        now=now,
        discard_after=issued.expires_at,
    )
    await session.commit()
    return EmailCodeRequestResponse()


@router.post("/email/verify", response_model=AuthSessionResponse)
async def verify_login_email_code(
    payload: AuthVerifyRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    notifications: Annotated[
        NotificationOutboxService,
        Depends(get_notification_outbox_service),
    ],
    methods: Annotated[AuthMethodRegistry, Depends(get_auth_method_registry)],
) -> AuthSessionResponse:
    method = methods.get("email")
    if not isinstance(method, EmailOtpAuthMethod):
        raise HTTPException(status_code=503, detail="Email authentication is unavailable")
    try:
        tokens = await method.verify_code(
            identity,
            session,
            email=payload.email,
            code=payload.code,
            now=_utc_now(),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except (ExpiredOtpError, InactiveUserError, InvalidEmailError, InvalidOtpError) as error:
        raise HTTPException(status_code=400, detail="Invalid code") from error
    if tokens.verified_challenge_id is not None:
        await notifications.cancel_auth_otp(
            session,
            challenge_ids=[tokens.verified_challenge_id],
            now=_utc_now(),
            reason="challenge_consumed",
        )
    await session.commit()
    _set_refresh_cookie(response, request.app.state.settings, tokens)
    return _session_response(tokens)


@router.post("/refresh", response_model=AuthSessionResponse)
async def refresh_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> AuthSessionResponse:
    _require_same_origin(request)
    cookie_name = request.app.state.settings.identity_refresh_cookie_name
    token = request.cookies.get(cookie_name)
    if not token:
        _clear_refresh_cookie(response, request.app.state.settings)
        raise _unauthorized()
    try:
        tokens = await identity.rotate_refresh_token(
            session,
            refresh_token=token,
            now=_utc_now(),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except (InactiveUserError, InvalidSessionError, RefreshTokenReuseError) as error:
        _clear_refresh_cookie(response, request.app.state.settings)
        raise _unauthorized() from error
    await session.commit()
    _set_refresh_cookie(response, request.app.state.settings, tokens)
    return _session_response(tokens)


@router.post("/session/migrate", response_model=AuthSessionResponse)
async def migrate_legacy_session(
    request: Request,
    response: Response,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer),
    ],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> AuthSessionResponse:
    _require_same_origin(request)
    grace_until = request.app.state.settings.identity_legacy_token_grace_until
    if (
        credentials is None
        or credentials.scheme.casefold() != "bearer"
        or grace_until is None
        or _utc_now() > ensure_utc(grace_until)
    ):
        raise _unauthorized()
    try:
        tokens = await identity.migrate_legacy_access_token(
            session,
            access_token=credentials.credentials,
            now=_utc_now(),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except (InactiveUserError, InvalidSessionError) as error:
        raise _unauthorized() from error
    await session.commit()
    _set_refresh_cookie(response, request.app.state.settings, tokens)
    return _session_response(tokens)


@router.post("/logout", response_model=LoggedOutResponse)
async def logout_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> LoggedOutResponse:
    _require_same_origin(request)
    refresh_token = request.cookies.get(request.app.state.settings.identity_refresh_cookie_name)
    if refresh_token:
        await identity.revoke_refresh_token(
            session,
            refresh_token=refresh_token,
            now=_utc_now(),
        )
        await session.commit()
    _clear_refresh_cookie(response, request.app.state.settings)
    return LoggedOutResponse()


@router.get("/me", response_model=AuthUserResponse)
async def get_profile(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> AuthUserResponse:
    await _require_permission(
        identity,
        session,
        user.id,
        PermissionCode.PROFILE_READ_OWN,
    )
    return _user_response(user)


@router.get("/access", response_model=AuthAccessResponse)
async def get_access(
    response: Response,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> AuthAccessResponse:
    snapshot = await identity.get_access_snapshot(session, user_id=user.id)
    response.headers["Cache-Control"] = "no-store"
    return AuthAccessResponse(
        roles=list(snapshot.roles),
        permissions=list(snapshot.permissions),
    )


@router.put("/me", response_model=AuthUserResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> AuthUserResponse:
    await _require_permission(
        identity,
        session,
        user.id,
        PermissionCode.PROFILE_WRITE_OWN,
    )
    field_mapping = {"height": "height_cm", "weight": "weight_kg"}
    provided_fields = {
        field_mapping.get(field, field) for field in payload.model_fields_set if field != "email"
    }
    try:
        updated = await identity.update_profile(
            session,
            user_id=user.id,
            changes=ProfileChanges(
                first_name=payload.first_name,
                last_name=payload.last_name,
                gender=payload.gender,
                birth_date=payload.birth_date,
                phone=payload.phone,
                height_cm=payload.height,
                weight_kg=payload.weight,
                provided_fields=frozenset(provided_fields),
            ),
            now=_utc_now(),
        )
    except (InvalidPhoneError, PhoneAlreadyUsedError) as error:
        raise HTTPException(status_code=400, detail="Invalid phone") from error
    await session.commit()
    return _user_response(updated)


@router.post("/me/email/request", response_model=EmailCodeRequestResponse)
async def request_profile_email_code(
    payload: AuthEmailRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    notifications: Annotated[
        NotificationOutboxService,
        Depends(get_notification_outbox_service),
    ],
) -> EmailCodeRequestResponse:
    await _require_permission(
        identity,
        session,
        user.id,
        PermissionCode.PROFILE_WRITE_OWN,
    )
    now = _utc_now()
    try:
        issued = await identity.request_email_change_otp(
            session,
            user_id=user.id,
            email=payload.email,
            now=now,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except EmailAlreadyUsedError as error:
        raise HTTPException(
            status_code=400,
            detail="Этот email уже используется другим аккаунтом",
        ) from error
    except OtpRateLimitError as error:
        raise HTTPException(
            status_code=429,
            detail="Too many code requests",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    except InvalidEmailError as error:
        raise HTTPException(status_code=400, detail="Invalid email") from error

    await notifications.cancel_auth_otp(
        session,
        challenge_ids=issued.invalidated_challenge_ids,
        now=now,
        reason="challenge_replaced",
    )
    await notifications.enqueue_auth_otp(
        session,
        recipient=issued.target_email,
        code=issued.code,
        purpose="email_change",
        expires_minutes=int(identity.policy.otp_lifetime.total_seconds() // 60),
        deduplication_key=f"otp:challenge:{issued.challenge_id}",
        now=now,
        discard_after=issued.expires_at,
    )
    await session.commit()
    return EmailCodeRequestResponse()


@router.post("/me/email/verify", response_model=AuthUserResponse)
async def verify_profile_email_code(
    payload: AuthVerifyRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    notifications: Annotated[
        NotificationOutboxService,
        Depends(get_notification_outbox_service),
    ],
) -> AuthUserResponse:
    await _require_permission(
        identity,
        session,
        user.id,
        PermissionCode.PROFILE_WRITE_OWN,
    )
    try:
        result = await identity.verify_email_change_otp(
            session,
            user_id=user.id,
            email=payload.email,
            code=payload.code,
            now=_utc_now(),
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except EmailAlreadyUsedError as error:
        raise HTTPException(
            status_code=400,
            detail="Этот email уже используется другим аккаунтом",
        ) from error
    except (ExpiredOtpError, InvalidEmailError, InvalidOtpError) as error:
        raise HTTPException(status_code=400, detail="Неверный код") from error
    await notifications.cancel_auth_otp(
        session,
        challenge_ids=[result.challenge_id],
        now=_utc_now(),
        reason="challenge_consumed",
    )
    await session.commit()
    return _user_response(result.user)


@router.delete("/me", response_model=DeletedResponse)
async def delete_profile(
    response: Response,
    request: Request,
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> DeletedResponse:
    await _require_permission(
        identity,
        session,
        user.id,
        PermissionCode.PROFILE_WRITE_OWN,
    )
    await identity.delete_profile(session, user_id=user.id, now=_utc_now())
    await session.commit()
    _clear_refresh_cookie(response, request.app.state.settings)
    return DeletedResponse()


@router.get("/orders", response_model=list[LegacyOrderResponse])
async def get_owned_orders(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    bridge: Annotated[
        OwnedOrderService,
        Depends(get_order_bridge_service),
    ],
) -> list[LegacyOrderResponse]:
    await _require_permission(
        identity,
        session,
        user.id,
        PermissionCode.ORDERS_READ_OWN,
    )
    orders = await bridge.list_owned_orders(session, user=user)
    await session.commit()
    return orders


async def _require_permission(
    identity: IdentityService,
    session: AsyncSession,
    user_id: int,
    permission: PermissionCode,
) -> None:
    try:
        await identity.require_permission(
            session,
            user_id=user_id,
            permission=permission,
        )
    except PermissionDeniedError as error:
        raise HTTPException(status_code=403, detail="Forbidden") from error


def _session_response(tokens: AuthSessionTokens) -> AuthSessionResponse:
    return AuthSessionResponse(
        token=tokens.access_token,
        user=_user_response(tokens.user),
    )


def _user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        gender=user.gender,
        birth_date=user.birth_date,
        height=_decimal_float(user.height_cm),
        weight=_decimal_float(user.weight_kg),
        created_at=user.created_at,
    )


def _decimal_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _set_refresh_cookie(
    response: Response,
    settings: Settings,
    tokens: AuthSessionTokens,
) -> None:
    max_age = max(1, int((tokens.refresh_expires_at - _utc_now()).total_seconds()))
    response.set_cookie(
        key=settings.identity_refresh_cookie_name,
        value=tokens.refresh_token,
        max_age=max_age,
        expires=tokens.refresh_expires_at,
        path="/api/auth",
        secure=settings.app_env in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION},
        httponly=True,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.identity_refresh_cookie_name,
        path="/api/auth",
        secure=settings.app_env in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION},
        httponly=True,
        samesite="lax",
    )


def _require_same_origin(request: Request) -> None:
    settings: Settings = request.app.state.settings
    origin = request.headers.get("origin")
    if origin is None and settings.app_env in {AppEnvironment.LOCAL, AppEnvironment.TEST}:
        return
    allowed = set(settings.cors_origin_list)
    public_url = urlsplit(settings.public_base_url)
    allowed.add(f"{public_url.scheme}://{public_url.netloc}")
    if (origin or "").rstrip("/") not in allowed:
        raise HTTPException(status_code=403, detail="Cross-site request rejected")


def _client_ip(request: Request) -> str | None:
    peer = request.client.host if request.client else None
    if not peer:
        return None
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return None
    if peer_address.is_private or peer_address.is_loopback:
        forwarded = request.headers.get("x-real-ip")
        if forwarded:
            try:
                return str(ipaddress.ip_address(forwarded.strip()))
            except ValueError:
                pass
    return str(peer_address)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={
            "Cache-Control": "no-store",
            "WWW-Authenticate": "Bearer",
        },
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
