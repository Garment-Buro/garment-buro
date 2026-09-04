from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass

from Crypto.Cipher import AES


class PartnerRequisitesEncryptionError(RuntimeError):
    pass


class PartnerRequisitesDecryptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EncryptedPartnerRequisites:
    ciphertext: str
    nonce: str
    tag: str
    key_version: int
    schema_version: int


class PartnerRequisitesCodec:
    """AES-256-GCM codec binding payout requisites to one partner profile."""

    SCHEMA_VERSION = 1

    def __init__(self, keys: dict[int, bytes], *, current_version: int) -> None:
        if current_version <= 0 or current_version not in keys:
            raise ValueError("Current partner requisites key version is missing")
        if any(version <= 0 for version in keys):
            raise ValueError("Every partner requisites key version must be positive")
        if any(len(key) != 32 for key in keys.values()):
            raise ValueError("Every partner requisites encryption key must contain 32 bytes")
        self._keys = dict(keys)
        self.current_version = current_version

    @classmethod
    def from_base64_keys(
        cls,
        encoded_keys: dict[int, str],
        *,
        current_version: int,
    ) -> PartnerRequisitesCodec:
        try:
            keys = {version: _decode(value) for version, value in encoded_keys.items()}
        except (binascii.Error, ValueError) as error:
            raise ValueError(
                "Partner requisites encryption keys must be URL-safe base64"
            ) from error
        return cls(keys, current_version=current_version)

    def encrypt(
        self,
        payload: dict[str, object],
        *,
        partner_id: int,
    ) -> EncryptedPartnerRequisites:
        if partner_id <= 0:
            raise PartnerRequisitesEncryptionError("Partner requisites context is invalid")
        try:
            serialized = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise PartnerRequisitesEncryptionError(
                "Partner requisites are not JSON serializable"
            ) from error

        key_version = self.current_version
        cipher = AES.new(self._keys[key_version], AES.MODE_GCM)
        cipher.update(
            self._aad(
                partner_id=partner_id,
                key_version=key_version,
                schema_version=self.SCHEMA_VERSION,
            )
        )
        ciphertext, tag = cipher.encrypt_and_digest(serialized)
        return EncryptedPartnerRequisites(
            ciphertext=_encode(ciphertext),
            nonce=_encode(cipher.nonce),
            tag=_encode(tag),
            key_version=key_version,
            schema_version=self.SCHEMA_VERSION,
        )

    def decrypt(
        self,
        payload: EncryptedPartnerRequisites,
        *,
        partner_id: int,
    ) -> dict[str, object]:
        key = self._keys.get(payload.key_version)
        if key is None:
            raise PartnerRequisitesDecryptionError(
                "Partner requisites encryption key version is unavailable"
            )
        try:
            cipher = AES.new(key, AES.MODE_GCM, nonce=_decode(payload.nonce))
            cipher.update(
                self._aad(
                    partner_id=partner_id,
                    key_version=payload.key_version,
                    schema_version=payload.schema_version,
                )
            )
            serialized = cipher.decrypt_and_verify(
                _decode(payload.ciphertext),
                _decode(payload.tag),
            )
            decoded = json.loads(serialized)
        except (binascii.Error, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise PartnerRequisitesDecryptionError(
                "Partner requisites authentication failed"
            ) from error
        if not isinstance(decoded, dict):
            raise PartnerRequisitesDecryptionError("Partner requisites must be an object")
        return decoded

    @staticmethod
    def digest(payload: dict[str, object]) -> str:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    @staticmethod
    def _aad(*, partner_id: int, key_version: int, schema_version: int) -> bytes:
        return (
            f"garment-buro-partner-requisites:partner:{partner_id}:"
            f"schema:{schema_version}:key:{key_version}"
        ).encode("ascii")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        f"{value}{padding}",
        altchars=b"-_",
        validate=True,
    )
