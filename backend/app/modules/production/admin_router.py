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
from app.modules.production.employee_schemas import EmployeeCodeResponse, EmployeeWrite, Station
from app.modules.production.employee_service import (
    EmployeeConflictError,
    EmployeeNotFoundError,
    ProductionEmployeeService,
)
from app.modules.production.inbox_models import AdminInboxKind
from app.modules.production.inbox_schemas import (
    AdminInboxPage,
    AdminInboxRead,
    AdminInboxUpdate,
    InboxPriority,
    InboxStatus,
)
from app.modules.production.inbox_service import (
    AdminInboxConflictError,
    AdminInboxNotFoundError,
    AdminInboxService,
)
from app.modules.production.security import can_administer, can_system_administer
from app.modules.production.ticket_routing import route_ticket
from app.modules.production.ticket_schemas import AdminTicketCreate, TicketReply, TicketRoute
from app.modules.production.ticket_service import TicketService

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


async def require_system_admin(
    request: Request,
    response: Response,
    session: Session,
    user: Annotated[User, Depends(get_production_user)],
):
    await require_admin(request, response, session, user)
    if not await can_system_administer(session, user.id):
        raise HTTPException(
            403,
            "Раздел доступен только системному администратору",
            headers={"Cache-Control": "no-store"},
        )
    return user


SystemAdmin = Annotated[User, Depends(require_system_admin)]


async def ticket_command(session, operation):
    try:
        result = await operation
        await session.commit()
        return result
    except AdminInboxNotFoundError as error:
        await session.rollback()
        raise HTTPException(404, "Тикет не найден") from error
    except AdminInboxConflictError as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error


@router.post("/tickets", status_code=201)
async def create_ticket(payload: AdminTicketCreate, admin: SystemAdmin, session: Session):
    from app.modules.production.inbox_service import SupportRateLimitError

    try:
        return await ticket_command(
            session, TicketService().create_for_customer(session, actor=admin, payload=payload)
        )
    except SupportRateLimitError as error:
        await session.rollback()
        raise HTTPException(429, str(error)) from error


@router.get("/tickets/{ticket_id}")
async def ticket_thread(
    ticket_id: int, admin: Admin, session: Session, after: int = Query(0, ge=0)
):
    try:
        service = TicketService()
        item = await service.item(session, ticket_id)
        if item.kind == AdminInboxKind.SUPPORT.value and not await can_system_administer(
            session, admin.id
        ):
            raise HTTPException(403, "Поддержка доступна только системному администратору")
        return await service.detail(session, item, admin=True, after=after)
    except AdminInboxNotFoundError as error:
        raise HTTPException(404, "Тикет не найден") from error


@router.post("/tickets/{ticket_id}/messages")
async def ticket_reply(ticket_id: int, payload: TicketReply, admin: Admin, session: Session):
    try:
        item = await TicketService().item(session, ticket_id)
    except AdminInboxNotFoundError as error:
        raise HTTPException(404, "Тикет не найден") from error
    if item.kind == AdminInboxKind.SUPPORT.value and not await can_system_administer(
        session, admin.id
    ):
        raise HTTPException(403, "Поддержка доступна только системному администратору")
    return await ticket_command(
        session,
        TicketService().reply(
            session, ticket_id=ticket_id, actor=admin, payload=payload, admin=True
        ),
    )


@router.post("/tickets/{ticket_id}/route")
async def ticket_route(ticket_id: int, payload: TicketRoute, admin: Admin, session: Session):
    return await ticket_command(session, route_ticket(session, ticket_id, admin, payload))


class ListQuery(BaseModel):
    q: str = Field(default="", max_length=100)
    status: str = Field(default="", max_length=32)
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=1000000)


class OrderListQuery(ListQuery):
    sort: Literal["created_at", "total", "client", "status", "payment_status"] = "created_at"
    direction: Literal["asc", "desc"] = "desc"


class PayoutListQuery(ListQuery):
    sort: Literal["created_at", "amount", "partner", "status"] = "created_at"
    direction: Literal["asc", "desc"] = "desc"


class EmployeeListQuery(ListQuery):
    status: Literal["active", "blocked", ""] = ""
    availability: Literal["available", "sick", "vacation", "absent", ""] = ""
    station: Station | Literal["production_admin", ""] = ""


class InboxListQuery(BaseModel):
    q: str = Field(default="", max_length=100)
    status: InboxStatus | Literal[""] = ""
    priority: InboxPriority | Literal[""] = ""
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=1000000)


@router.get("/stats")
async def statistics(_admin: SystemAdmin, session: Session):
    return await ProductionAdminReads().stats(session)


@router.get("/orders")
async def orders(_admin: Admin, session: Session, query: Annotated[OrderListQuery, Query()]):
    return await ProductionAdminReads().orders(session, **query.model_dump())


@router.get("/orders/{order_id}")
async def order(order_id: int, _admin: Admin, session: Session):
    result = await ProductionAdminReads().order(session, order_id)
    if result is None:
        raise HTTPException(404, "Заказ не найден")
    return result


@router.get("/users")
async def users(
    request: Request,
    _admin: SystemAdmin,
    session: Session,
    query: Annotated[EmployeeListQuery, Query()],
):
    return await ProductionAdminReads().users(
        session, **query.model_dump(), pepper=employee_pepper(request)
    )


@router.get("/employees")
async def employees(
    request: Request,
    _admin: SystemAdmin,
    session: Session,
    query: Annotated[EmployeeListQuery, Query()],
):
    return await ProductionAdminReads().employees(
        session, **query.model_dump(), pepper=employee_pepper(request)
    )


def employee_pepper(request: Request) -> str:
    return request.app.state.settings.require_secret("identity_otp_pepper", "IDENTITY_OTP_PEPPER")


async def inbox_list(kind: str, session: Session, query: InboxListQuery):
    return await AdminInboxService().list(session, kind=kind, **query.model_dump())


async def inbox_item(kind: str, item_id: int, session: Session):
    try:
        return await AdminInboxService().get(session, item_id=item_id, kind=kind)
    except AdminInboxNotFoundError as error:
        raise HTTPException(404, "Обращение не найдено") from error


async def update_inbox_item(
    kind: str,
    item_id: int,
    payload: AdminInboxUpdate,
    admin: User,
    session: Session,
):
    try:
        result = await AdminInboxService().update(
            session,
            item_id=item_id,
            kind=kind,
            payload=payload,
            actor_user_id=admin.id,
        )
        await session.commit()
        return result
    except AdminInboxNotFoundError as error:
        await session.rollback()
        raise HTTPException(404, "Обращение не найдено") from error
    except AdminInboxConflictError as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error


@router.get("/support", response_model=AdminInboxPage)
async def support(_admin: SystemAdmin, session: Session, query: Annotated[InboxListQuery, Query()]):
    return await inbox_list(AdminInboxKind.SUPPORT.value, session, query)


@router.get("/support/{item_id}", response_model=AdminInboxRead)
async def support_item(item_id: int, _admin: SystemAdmin, session: Session):
    return await inbox_item(AdminInboxKind.SUPPORT.value, item_id, session)


@router.patch("/support/{item_id}", response_model=AdminInboxRead)
async def update_support(
    item_id: int, payload: AdminInboxUpdate, admin: SystemAdmin, session: Session
):
    return await update_inbox_item(AdminInboxKind.SUPPORT.value, item_id, payload, admin, session)


@router.get("/problems", response_model=AdminInboxPage)
async def problems(_admin: Admin, session: Session, query: Annotated[InboxListQuery, Query()]):
    return await inbox_list(AdminInboxKind.PRODUCTION_PROBLEM.value, session, query)


@router.get("/problems/{item_id}", response_model=AdminInboxRead)
async def problem_item(item_id: int, _admin: Admin, session: Session):
    return await inbox_item(AdminInboxKind.PRODUCTION_PROBLEM.value, item_id, session)


@router.patch("/problems/{item_id}", response_model=AdminInboxRead)
async def update_problem(item_id: int, payload: AdminInboxUpdate, admin: Admin, session: Session):
    return await update_inbox_item(
        AdminInboxKind.PRODUCTION_PROBLEM.value, item_id, payload, admin, session
    )


@router.post("/employees", response_model=EmployeeCodeResponse)
async def create_employee(
    payload: EmployeeWrite, request: Request, admin: SystemAdmin, session: Session
):
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
    admin: SystemAdmin,
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
async def rotate_employee_code(
    user_id: int, request: Request, admin: SystemAdmin, session: Session
):
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
async def clients(_admin: SystemAdmin, session: Session, query: Annotated[ListQuery, Query()]):
    return await ProductionAdminReads().clients(session, **query.model_dump(exclude={"status"}))


@router.get("/payouts")
async def payouts(
    _admin: SystemAdmin, session: Session, query: Annotated[PayoutListQuery, Query()]
):
    return await ProductionAdminReads().payouts(session, **query.model_dump())


class PayoutReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_status: Literal["requested", "approved"]
    status: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=500)


@router.post("/payouts/{payout_id}/review")
async def review(
    payout_id: int,
    payload: PayoutReview,
    request: Request,
    admin: SystemAdmin,
    session: Session,
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
