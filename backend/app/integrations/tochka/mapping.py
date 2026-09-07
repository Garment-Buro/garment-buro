from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.modules.partners.schemas import PartnerRequisitesRequest


def bank_request(
    *,
    settings: Settings,
    payout_id: int,
    amount: Decimal,
    requisites: PartnerRequisitesRequest,
    purpose: str,
    now: datetime,
) -> tuple[dict[str, object], bytes]:
    if requisites.entity_type != "sole_proprietor":
        raise ValueError("Tochka partner payouts currently support sole proprietors only")
    if (
        not requisites.settlement_account.startswith("40802")
        or requisites.settlement_account[5:8] != "810"
    ):
        raise ValueError("A RUB sole proprietor settlement account is required")
    if not requisites.tax_id.isascii() or len(requisites.tax_id) != 12:
        raise ValueError("A 12-digit sole proprietor tax ID is required")
    if any(
        not value.isascii() or not value.isdigit()
        for value in (
            requisites.tax_id,
            requisites.bic,
            requisites.settlement_account,
            requisites.correspondent_account,
        )
    ):
        raise ValueError("Bank requisites must contain ASCII digits")
    if (
        not amount.is_finite()
        or amount <= 0
        or amount >= Decimal("10000000000")
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise ValueError("Invalid payout amount")
    purpose = f"{purpose} [GB-PAYOUT-{payout_id}]"
    if len(purpose) > 210:
        raise ValueError("Payment purpose exceeds bank limit")
    payload = {
        "Data": {
            "accountCode": (
                "12345810901234567890"
                if settings.tochka_environment == "sandbox"
                else settings.secret_value(settings.tochka_account_code)
            ),
            "bankCode": "044525104"
            if settings.tochka_environment == "sandbox"
            else settings.tochka_bank_code,
            "counterpartyBankBic": requisites.bic,
            "counterpartyAccountNumber": requisites.settlement_account,
            "counterpartyINN": requisites.tax_id,
            "counterpartyKPP": "0",
            "counterpartyName": requisites.recipient_name,
            "counterpartyBankCorrAccount": requisites.correspondent_account,
            # OpenAPI requires a JSON number. Decimal remains the domain/accounting type.
            "paymentAmount": float(amount),
            "paymentDate": now.astimezone(ZoneInfo("Europe/Moscow")).date().isoformat(),
            "paymentPriority": "5",
            "paymentPurpose": purpose,
        }
    }
    return payload, json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()
