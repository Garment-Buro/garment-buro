"""Personal floor codes. These credentials never create a general identity session."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.modules.identity.models import SecurityAuditEvent, User
from app.modules.production.auth_models import (
    ProductionCredential,
    ProductionLoginLimit,
    ProductionSession,
)
from app.modules.production.security import ProductionDenied, can_administer, stations_for_user

PREFIXES = {
    "admin": "99",
    "tech": "0",
    "kit": "1",
    "cut": "2",
    "dtf": "3",
    "workshop": "4",
    "application": "4",
    "sewing": "5",
    "press": "6",
    "qc": "7",
    "packing": "8",
    "shipping": "9",
}
SESSION_SECONDS = 8 * 60 * 60


def code_digest(code: str, pepper: str) -> str:
    return hmac.new(
        pepper.encode(), ("production-pin:" + code).encode(), hashlib.sha256
    ).hexdigest()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def limit_login(session, *, client_ip: str, pepper: str, now: datetime) -> bool:
    """Atomic, shared across workers; fail closed if the database is unavailable."""
    bucket = int(now.timestamp()) // 900
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    allowed = True
    for scope, maximum in (("global", 100), ("ip:" + client_ip, 10)):
        key = code_digest(f"limit:{scope}:{bucket}", pepper)
        await session.execute(
            insert(ProductionLoginLimit)
            .values(key=key, attempts=0, expires_at=now + timedelta(minutes=30))
            .on_conflict_do_nothing(index_elements=["key"])
        )
        count = await session.scalar(
            update(ProductionLoginLimit)
            .where(ProductionLoginLimit.key == key)
            .values(attempts=ProductionLoginLimit.attempts + 1)
            .returning(ProductionLoginLimit.attempts)
        )
        allowed = allowed and count <= maximum
    await session.execute(delete(ProductionLoginLimit).where(ProductionLoginLimit.expires_at < now))
    await session.commit()  # Failed logins must not roll back rate-limit counters.
    return allowed


async def issue_code(session, *, user_id: int, station: str, pepper: str) -> str:
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or user.status != "active" or station not in PREFIXES:
        raise ValueError("Active employee and known station are required")
    allowed = (
        await can_administer(session, user_id)
        if station == "admin"
        else station in await stations_for_user(session, user_id)
    )
    if not allowed:
        raise ValueError("Assign the employee's station role before issuing a code")
    # Retain old digests so a revoked code can never be reassigned to another employee.
    for _ in range(100):
        digits = 6 if station == "admin" else 5
        code = PREFIXES[station] + str(secrets.randbelow(10**digits)).zfill(digits)
        digest = code_digest(code, pepper)
        if not await session.scalar(
            select(ProductionCredential.id).where(ProductionCredential.code_digest == digest)
        ):
            break
    else:
        raise ValueError("Could not allocate a unique code")
    await revoke_code(session, user_id=user_id)
    session.add(
        ProductionCredential(user_id=user_id, station=station, code_digest=digest, active=True)
    )
    await (
        session.flush()
    )  # A concurrent collision aborts safely; never disclose an uncommitted code.
    session.add(
        SecurityAuditEvent(
            event_type="production.code_issued",
            subject_user_id=user_id,
            details={"station": station, "source": "operator_cli"},
        )
    )
    return code


async def revoke_code(session, *, user_id: int) -> None:
    await session.scalar(select(User).where(User.id == user_id).with_for_update())
    await session.execute(
        update(ProductionCredential)
        .where(ProductionCredential.user_id == user_id)
        .values(active=False)
    )
    session.add(
        SecurityAuditEvent(
            event_type="production.code_revoked",
            subject_user_id=user_id,
            details={"source": "operator_cli"},
        )
    )


async def login(session, *, code: str, pepper: str, now: datetime) -> str | None:
    credential = await session.scalar(
        select(ProductionCredential).where(
            ProductionCredential.code_digest == code_digest(code, pepper),
            ProductionCredential.active.is_(True),
        )
    )
    if credential is None or await employee_for_credential(session, credential) is None:
        return None
    token = secrets.token_urlsafe(32)
    session.add(
        ProductionSession(
            digest=token_digest(token),
            credential_id=credential.id,
            expires_at=now + timedelta(seconds=SESSION_SECONDS),
        )
    )
    session.add(
        SecurityAuditEvent(
            event_type="production.code_login",
            actor_user_id=credential.user_id,
            subject_user_id=credential.user_id,
            details={"station": credential.station},
        )
    )
    await session.execute(delete(ProductionSession).where(ProductionSession.expires_at < now))
    await session.commit()
    return token


async def employee_for_credential(session, credential):
    user = await session.get(User, credential.user_id)
    if not credential.active or user is None or user.status != "active":
        return None
    if credential.station == "admin":
        return user if await can_administer(session, user.id) else None
    try:
        stations = await stations_for_user(session, user.id)
    except ProductionDenied:
        return None
    return user if credential.station in stations else None


async def resolve_session(session, token: str):
    credential = await resolve_credential(session, token)
    return await employee_for_credential(session, credential) if credential else None


async def resolve_credential(session, token: str):
    return await session.scalar(
        select(ProductionCredential)
        .join(ProductionSession, ProductionSession.credential_id == ProductionCredential.id)
        .where(
            ProductionSession.digest == token_digest(token),
            ProductionSession.expires_at > datetime.now(timezone.utc),
        )
    )
