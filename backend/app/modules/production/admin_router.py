from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.identity.models import SecurityAuditEvent, User
from app.modules.partners.router import get_partner_service
from app.modules.partners.service import (
    PartnerNotFoundError,
    PartnerPayoutStateError,
    PartnerProgramDisabledError,
)
from app.modules.production.admin_reads import ProductionAdminReads
from app.modules.production.auth_router import get_production_user
from app.modules.production.employee_schemas import EmployeeCodeResponse, EmployeeWrite
from app.modules.production.employee_service import (
    EmployeeConflictError,
    EmployeeNotFoundError,
    ProductionEmployeeService,
)
from app.modules.production.security import can_administer

router = APIRouter(prefix="/admin", tags=["production-admin"])
Session = Annotated[AsyncSession, Depends(get_database_session)]


async def require_admin(
    request: Request,
    response: Response,
    session: Session,
    user: Annotated[User, Depends(get_production_user)],
):
    response.headers["Cache-Control"] = "no-store"
    if getattr(request.state, "production_station", None) != "admin" or not await can_administer(
        session, user.id
    ):
        raise HTTPException(
            403, "Нужен личный код администратора", headers={"Cache-Control": "no-store"}
        )
    return user


Admin = Annotated[User, Depends(require_admin)]


class ListQuery(BaseModel):
    q: str = Field(default="", max_length=100)
    status: str = Field(default="", max_length=32)
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=1000000)


@router.get("/stats")
async def statistics(_admin: Admin, session: Session):
    return await ProductionAdminReads().stats(session)


@router.get("/orders")
async def orders(_admin: Admin, session: Session, query: Annotated[ListQuery, Query()]):
    return await ProductionAdminReads().orders(session, **query.model_dump())


@router.get("/orders/{order_id}")
async def order(order_id: int, _admin: Admin, session: Session):
    result = await ProductionAdminReads().order(session, order_id)
    if result is None:
        raise HTTPException(404, "Заказ не найден")
    return result


@router.get("/users")
async def users(_admin: Admin, session: Session, query: Annotated[ListQuery, Query()]):
    return await ProductionAdminReads().users(session, **query.model_dump())


@router.get("/employees")
async def employees(_admin: Admin, session: Session, query: Annotated[ListQuery, Query()]):
    return await ProductionAdminReads().employees(session, **query.model_dump())


def employee_pepper(request: Request) -> str:
    return request.app.state.settings.require_secret("identity_otp_pepper", "IDENTITY_OTP_PEPPER")


@router.post("/employees", response_model=EmployeeCodeResponse)
async def create_employee(payload: EmployeeWrite, request: Request, admin: Admin, session: Session):
    try:
        employee, code = await ProductionEmployeeService().create(
            session,
            payload=payload,
            actor_id=admin.id,
            pepper=employee_pepper(request),
        )
        return {"employee": employee, "code": code}
    except EmployeeConflictError as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error


@router.put("/employees/{user_id}", response_model=EmployeeCodeResponse)
async def update_employee(
    user_id: int,
    payload: EmployeeWrite,
    request: Request,
    admin: Admin,
    session: Session,
):
    try:
        employee, code = await ProductionEmployeeService().update(
            session,
            user_id=user_id,
            payload=payload,
            actor_id=admin.id,
            pepper=employee_pepper(request),
        )
        return {"employee": employee, "code": code}
    except EmployeeNotFoundError as error:
        raise HTTPException(404, "Сотрудник не найден") from error
    except EmployeeConflictError as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error


@router.post("/employees/{user_id}/code", response_model=EmployeeCodeResponse)
async def rotate_employee_code(user_id: int, request: Request, admin: Admin, session: Session):
    try:
        employee, code = await ProductionEmployeeService().rotate_code(
            session,
            user_id=user_id,
            actor_id=admin.id,
            pepper=employee_pepper(request),
        )
        return {"employee": employee, "code": code}
    except EmployeeNotFoundError as error:
        raise HTTPException(404, "Сотрудник не найден") from error
    except EmployeeConflictError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/clients")
async def clients(_admin: Admin, session: Session, query: Annotated[ListQuery, Query()]):
    return await ProductionAdminReads().clients(session, **query.model_dump(exclude={"status"}))


@router.get("/payouts")
async def payouts(_admin: Admin, session: Session, query: Annotated[ListQuery, Query()]):
    return await ProductionAdminReads().payouts(session, **query.model_dump())


class PayoutReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_status: Literal["requested", "approved"]
    status: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=500)


@router.post("/payouts/{payout_id}/review")
async def review(
    payout_id: int, payload: PayoutReview, request: Request, admin: Admin, session: Session
):
    partners = get_partner_service(request)
    try:
        payout = await partners.repository.get_payout_for_update(session, payout_id=payout_id)
        if payout is None:
            raise PartnerNotFoundError()
        if payout.status != payload.expected_status:
            raise PartnerPayoutStateError()
        payout = await partners.review_payout(
            session,
            payout_id=payout_id,
            status=payload.status,
            note=payload.note,
            actor_user_id=admin.id,
        )
        session.add(
            SecurityAuditEvent(
                event_type="production.payout_review",
                actor_user_id=admin.id,
                details={
                    "payout_id": payout.id,
                    "from": payload.expected_status,
                    "to": payout.status,
                },
            )
        )
        await session.commit()
        return {"id": payout.id, "status": payout.status}
    except PartnerNotFoundError as error:
        raise HTTPException(404, "Заявка не найдена") from error
    except PartnerPayoutStateError as error:
        await session.rollback()
        raise HTTPException(
            409, "Заявка уже изменена или передана в банк. Обновите список."
        ) from error
    except PartnerProgramDisabledError as error:
        raise HTTPException(503, "Партнёрская программа выключена") from error
