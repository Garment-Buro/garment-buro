from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.partners.requisites_crypto import (
    EncryptedPartnerRequisites,
    PartnerRequisitesCodec,
    PartnerRequisitesDecryptionError,
)
from app.modules.partners.schemas import PartnerRequisitesRequest

KEY = "bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4="


def test_partner_requisites_are_encrypted_and_bound_to_partner() -> None:
    codec = PartnerRequisitesCodec.from_base64_keys({1: KEY}, current_version=1)
    clear_payload = {
        "entity_type": "sole_proprietor",
        "recipient_name": "ИП Иванов Иван Иванович",
        "tax_id": "123456789012",
        "kpp": None,
        "bank_name": "Тестовый банк",
        "bic": "044525225",
        "correspondent_account": "30101810400000000225",
        "settlement_account": "40802810900000000001",
    }

    encrypted = codec.encrypt(clear_payload, partner_id=7)

    assert clear_payload["recipient_name"] not in encrypted.ciphertext
    assert codec.decrypt(encrypted, partner_id=7) == clear_payload
    with pytest.raises(PartnerRequisitesDecryptionError):
        codec.decrypt(encrypted, partner_id=8)


def test_partner_requisites_reject_tampered_ciphertext() -> None:
    codec = PartnerRequisitesCodec.from_base64_keys({1: KEY}, current_version=1)
    encrypted = codec.encrypt({"tax_id": "123456789012"}, partner_id=7)
    replacement = "A" if encrypted.ciphertext[0] != "A" else "B"
    tampered = EncryptedPartnerRequisites(
        ciphertext=f"{replacement}{encrypted.ciphertext[1:]}",
        nonce=encrypted.nonce,
        tag=encrypted.tag,
        key_version=encrypted.key_version,
        schema_version=encrypted.schema_version,
    )

    with pytest.raises(PartnerRequisitesDecryptionError):
        codec.decrypt(tampered, partner_id=7)


def test_partner_requisites_validate_entity_specific_tax_fields() -> None:
    with pytest.raises(ValidationError):
        PartnerRequisitesRequest(
            entity_type="legal_entity",
            recipient_name="ООО Тест",
            tax_id="123456789012",
            bank_name="Тестовый банк",
            bic="044525225",
            correspondent_account="30101810400000000225",
            settlement_account="40702810900000000001",
        )

    payload = PartnerRequisitesRequest(
        entity_type="legal_entity",
        recipient_name="ООО Тест",
        tax_id="1234567890",
        kpp="123456789",
        bank_name="Тестовый банк",
        bic="044525225",
        correspondent_account="30101810400000000225",
        settlement_account="40702810900000000001",
    )
    assert payload.kpp == "123456789"
