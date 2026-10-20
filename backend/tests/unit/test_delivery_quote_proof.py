from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest

from app.core.config import Settings
from app.modules.delivery.quote_proof import DeliveryQuoteProof, InvalidDeliveryQuoteError
from app.modules.delivery.quote_service import PreparedCdekQuote

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
PREPARED = PreparedCdekQuote(
    body=b"{}",
    sha256="b" * 64,
    tariff_code=136,
    request_sha256="a" * 64,
    delivery_city="Москва",
    delivery_address="Тверская,1",
    cdek_point_code="MSK1",
)


def test_quote_proof_binds_amount_request_purpose_and_expiry():
    proof = DeliveryQuoteProof(Settings(_env_file=None, jwt_secret="j" * 32))
    token = proof.issue(PREPARED, Decimal("450.25"), now=NOW)
    assert proof.verify(token, PREPARED, now=NOW + timedelta(minutes=14)) == Decimal("450.25")
    assert "Тверская" not in repr(jwt.decode(token, options={"verify_signature": False}))
    for at in [NOW - timedelta(minutes=1), NOW + timedelta(minutes=15)]:
        with pytest.raises(InvalidDeliveryQuoteError):
            proof.verify(token, PREPARED, now=at)
    changed = PreparedCdekQuote(
        body=PREPARED.body,
        sha256=PREPARED.sha256,
        tariff_code=136,
        request_sha256="c" * 64,
        delivery_city="Москва",
        delivery_address="Другой адрес",
        cdek_point_code="MSK2",
    )
    with pytest.raises(InvalidDeliveryQuoteError):
        proof.verify(token, changed, now=NOW)
    claims = jwt.decode(token, options={"verify_signature": False})
    identity_key_token = jwt.encode(claims, "j" * 32, algorithm="HS256")
    with pytest.raises(InvalidDeliveryQuoteError):
        proof.verify(identity_key_token, PREPARED, now=NOW)
    with pytest.raises(InvalidDeliveryQuoteError):
        DeliveryQuoteProof(Settings(_env_file=None, jwt_secret="x" * 32)).verify(
            token, PREPARED, now=NOW
        )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "10000000000.00", "0.001"])
def test_quote_proof_rejects_invalid_provider_amount(value):
    proof = DeliveryQuoteProof(Settings(_env_file=None, jwt_secret="j" * 32))
    with pytest.raises(InvalidDeliveryQuoteError):
        proof.issue(PREPARED, Decimal(value), now=NOW)
