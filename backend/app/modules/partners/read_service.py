import base64
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.security import ensure_utc
from app.modules.partners.read_repository import PartnerReadRepository
from app.modules.partners.read_schemas import (
    AdminPartnerPage,
    AdminPartnerPosition,
    AdminPartnerQuery,
    PartnerPayoutPage,
    PartnerPayoutPosition,
    PartnerPayoutQuery,
)
from app.modules.partners.schemas import PartnerPayoutResponse, PartnerProfileResponse


class InvalidPartnerReadCursor(ValueError):
    pass


class PartnerReadService:
    @staticmethod
    async def profiles(session: AsyncSession, query: AdminPartnerQuery) -> AdminPartnerPage:
        filters = hashlib.sha256(
            query.model_dump_json(exclude={"cursor", "limit"}).encode()
        ).hexdigest()
        after_id = None
        if query.cursor is not None:
            try:
                position = AdminPartnerPosition.model_validate_json(
                    base64.b64decode(query.cursor, altchars=b"-_", validate=True)
                )
                if position.filters != filters:
                    raise ValueError("Different profile filters")
                after_id = position.id
            except ValueError as error:
                raise InvalidPartnerReadCursor("Invalid profile cursor") from error
        records = await PartnerReadRepository.profile_page(session, query, after_id)
        page, cursor = records[: query.limit], None
        if len(records) > query.limit:
            cursor = base64.urlsafe_b64encode(
                AdminPartnerPosition(version=1, kind="profiles", id=page[-1]["id"], filters=filters)
                .model_dump_json()
                .encode()
            ).decode()
        return AdminPartnerPage(
            items=[PartnerProfileResponse.model_validate(row) for row in page], next_cursor=cursor
        )

    @staticmethod
    async def payouts(
        session: AsyncSession, partner_id: int, query: PartnerPayoutQuery
    ) -> PartnerPayoutPage:
        position = None
        if query.cursor is not None:
            try:
                position = PartnerPayoutPosition.model_validate_json(
                    base64.b64decode(query.cursor, altchars=b"-_", validate=True)
                )
                if position.partner_id != partner_id:
                    raise ValueError("Different payout owner")
            except ValueError as error:
                raise InvalidPartnerReadCursor("Invalid payout cursor") from error
        records = await PartnerReadRepository.payout_page(
            session, partner_id, query.limit, position
        )
        page, cursor = records[: query.limit], None
        if len(records) > query.limit:
            cursor = base64.urlsafe_b64encode(
                PartnerPayoutPosition(
                    version=1,
                    kind="payouts",
                    partner_id=partner_id,
                    id=page[-1]["id"],
                    created_at=ensure_utc(page[-1]["created_at"]),
                )
                .model_dump_json()
                .encode()
            ).decode()
        return PartnerPayoutPage(
            items=[PartnerPayoutResponse.model_validate(row) for row in page], next_cursor=cursor
        )
