from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.bank_payouts.repository import BankPayoutRepository
from app.modules.bank_payouts.schemas import (
    BankPayoutAdminResponse,
    BankPayoutCreate,
    BankPayoutSummary,
)
from app.modules.bank_payouts.service import (
    BankPayoutConflict,
    BankPayoutDisabled,
    BankPayoutNotFound,
    PartnerBankPayoutService,
)
from app.modules.identity.models import PermissionCode, User
from app.modules.identity.router import get_current_identity_user, get_identity_service
from app.modules.identity.service import IdentityService
from app.modules.partners.models import PartnerPayoutRequest
from app.modules.partners.requisites_crypto import PartnerRequisitesDecryptionError
from app.modules.partners.router import _require_permission, get_partner_service
from app.modules.partners.service import PartnerProgramService

router = APIRouter(tags=["partner-bank-payouts"])
ADMIN_PATH = "/api/admin/partners/payouts/{payout_id}/bank-payment"
Session = Annotated[AsyncSession, Depends(get_database_session)]


async def require_bank_admin(
    user: Annotated[User, Depends(get_current_identity_user)],
    session: Session,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> User:
    await _require_permission(identity, session, user.id, PermissionCode.PARTNERS_MANAGE)
    return user


def bank_service(request: Request) -> PartnerBankPayoutService:
    service = getattr(request.app.state, "partner_bank_payout_service", None)
    if not isinstance(service, PartnerBankPayoutService):
        raise HTTPException(503, "Tochka payouts are not enabled")
    return service


@router.get(ADMIN_PATH, response_model=BankPayoutAdminResponse)
async def get_bank_payment(
    payout_id: int,
    response: Response,
    session: Session,
    user: Annotated[User, Depends(require_bank_admin)],
) -> BankPayoutAdminResponse:
    response.headers["Cache-Control"] = "no-store"
    payment = await BankPayoutRepository().get(session, payout_id)
    if payment is None:
        raise HTTPException(404, "Bank operation was not found")
    return BankPayoutAdminResponse.model_validate(payment)


@router.post(ADMIN_PATH, response_model=BankPayoutAdminResponse)
async def create_bank_payment(
    payout_id: int,
    command: BankPayoutCreate,
    response: Response,
    session: Session,
    user: Annotated[User, Depends(require_bank_admin)],
    service: Annotated[PartnerBankPayoutService, Depends(bank_service)],
) -> BankPayoutAdminResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        payment = await service.create(
            session, payout_id=payout_id, command=command, actor_user_id=user.id
        )
        return BankPayoutAdminResponse.model_validate(payment)
    except BankPayoutNotFound as error:
        raise HTTPException(404, str(error)) from error
    except BankPayoutConflict as error:
        raise HTTPException(409, str(error)) from error
    except (BankPayoutDisabled, PartnerRequisitesDecryptionError) as error:
        raise HTTPException(503, "Bank payouts or requisites are unavailable") from error
    except SQLAlchemyError as error:
        await session.rollback()
        raise HTTPException(
            503, "Bank operation requires reconciliation; do not repeat with a new payout"
        ) from error


@router.post(ADMIN_PATH + "/refresh", response_model=BankPayoutAdminResponse)
async def refresh_bank_payment(
    payout_id: int,
    response: Response,
    session: Session,
    user: Annotated[User, Depends(require_bank_admin)],
    service: Annotated[PartnerBankPayoutService, Depends(bank_service)],
) -> BankPayoutAdminResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        return BankPayoutAdminResponse.model_validate(
            await service.reconcile(session, payout_id=payout_id)
        )
    except BankPayoutNotFound as error:
        raise HTTPException(404, str(error)) from error
    except BankPayoutConflict as error:
        raise HTTPException(409, str(error)) from error
    except SQLAlchemyError as error:
        await session.rollback()
        raise HTTPException(503, "Bank reconciliation is unavailable") from error
    except BankPayoutDisabled as error:
        raise HTTPException(503, "Bank reconciliation is disabled") from error


@router.get("/api/partner/payouts/{payout_id}/bank-payment", response_model=BankPayoutSummary)
async def get_own_bank_payment(
    payout_id: int,
    response: Response,
    session: Session,
    user: Annotated[User, Depends(get_current_identity_user)],
    partners: Annotated[PartnerProgramService, Depends(get_partner_service)],
) -> BankPayoutSummary:
    response.headers["Cache-Control"] = "no-store"
    profile = await partners.repository.get_profile_by_user(session, user_id=user.id)
    payout = await session.get(PartnerPayoutRequest, payout_id)
    if profile is None or payout is None or payout.partner_id != profile.id:
        raise HTTPException(404, "Payout request was not found")
    payment = await BankPayoutRepository().get(session, payout_id)
    if payment is None:
        raise HTTPException(404, "Bank operation was not found")
    # Partner never receives the payer's bank signing link or raw bank credentials.
    return BankPayoutSummary.model_validate(payment)
