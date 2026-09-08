from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppEnvironment
from app.db.session import get_database_session
from app.modules.identity.router import _client_ip, _require_same_origin
from app.modules.production import auth_service
from app.modules.production.auth_models import ProductionSession

router = APIRouter(prefix="/auth", tags=["production-auth"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
COOKIE = "gb_production_session"
COOKIE_PATH = "/api/production"


class CodeLogin(BaseModel):
    code: str = Field(pattern=r"^(?:[0-9]{6}|99[0-9]{6})$", repr=False)


def enabled(request: Request):
    if not request.app.state.settings.production_terminal_enabled:
        raise HTTPException(503, "Производственный терминал пока выключен")


async def get_production_user(request: Request, session: Session):
    enabled(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        _require_same_origin(request)
    token = request.cookies.get(COOKIE, "")
    credential = await auth_service.resolve_credential(session, token) if token else None
    user = await auth_service.employee_for_credential(session, credential) if credential else None
    if user is None:
        raise HTTPException(401, "Войдите по личному коду сотрудника")
    request.state.production_station = credential.station
    return user


@router.post("/login")
async def login(payload: CodeLogin, request: Request, response: Response, session: Session):
    enabled(request)
    _require_same_origin(request)
    settings = request.app.state.settings
    pepper = settings.require_secret("identity_otp_pepper", "IDENTITY_OTP_PEPPER")
    now = datetime.now(timezone.utc)
    if not await auth_service.limit_login(
        session, client_ip=_client_ip(request) or "unknown", pepper=pepper, now=now
    ):
        raise HTTPException(
            429, "Слишком много попыток. Повторите через 15 минут.", headers={"Retry-After": "900"}
        )
    token = await auth_service.login(session, code=payload.code, pepper=pepper, now=now)
    if token is None:
        raise HTTPException(401, "Неверный код или доступ отключён")
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        COOKIE,
        token,
        max_age=auth_service.SESSION_SECONDS,
        path=COOKIE_PATH,
        secure=settings.app_env in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION},
        httponly=True,
        samesite="strict",
    )
    return {"status": "authenticated"}


@router.post("/logout")
async def logout(request: Request, response: Response, session: Session):
    _require_same_origin(request)
    token = request.cookies.get(COOKIE)
    if token:
        await session.execute(
            delete(ProductionSession).where(
                ProductionSession.digest == auth_service.token_digest(token)
            )
        )
        await session.commit()
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    response.headers["Cache-Control"] = "no-store"
    return {"status": "logged_out"}
