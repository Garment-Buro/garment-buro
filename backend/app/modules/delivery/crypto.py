from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass

from Crypto.Cipher import AES


class CdekRequestEncryptionError(RuntimeError):
    pass


class CdekRequestDecryptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EncryptedCdekRequest:
    ciphertext: str
    nonce: str
    tag: str
    key_version: int


class CdekRequestCodec:
    """AES-256-GCM codec binding private request bytes to their order and digest."""

    def __init__(self, keys: dict[int, bytes], *, current_version: int) -> None:
        if current_version <= 0 or current_version not in keys:
            raise ValueError("Current CDEK request key version is missing")
        if any(version <= 0 for version in keys):
            raise ValueError("Every CDEK request key version must be positive")
        if any(len(key) != 32 for key in keys.values()):
            raise ValueError("Every CDEK request encryption key must contain 32 bytes")
        self._keys = dict(keys)
        self.current_version = current_version

    @classmethod
    def from_base64_key(
        cls,
        encoded_key: str,
        *,
        key_version: int = 1,
    ) -> CdekRequestCodec:
        return cls.from_base64_keys(
            {key_version: encoded_key},
            current_version=key_version,
        )

    @classmethod
    def from_base64_keys(
        cls,
        encoded_keys: dict[int, str],
        *,
        current_version: int,
    ) -> CdekRequestCodec:
        try:
            keys = {version: _decode(value) for version, value in encoded_keys.items()}
        except (binascii.Error, ValueError) as error:
            raise ValueError("CDEK request encryption keys must be URL-safe base64") from error
        return cls(keys, current_version=current_version)

    def encrypt(
        self,
        body: bytes,
        *,
        order_id: int,
        request_sha256: str,
        schema_version: int,
    ) -> EncryptedCdekRequest:
        self._validate_context(
            body,
            order_id=order_id,
            request_sha256=request_sha256,
            schema_version=schema_version,
        )
        version = self.current_version
        cipher = AES.new(self._keys[version], AES.MODE_GCM)
        cipher.update(
            self._aad(
                order_id=order_id,
                request_sha256=request_sha256,
                schema_version=schema_version,
                key_version=version,
            )
        )
        ciphertext, tag = cipher.encrypt_and_digest(body)
        return EncryptedCdekRequest(
            ciphertext=_encode(ciphertext),
            nonce=_encode(cipher.nonce),
            tag=_encode(tag),
            key_version=version,
        )

    def decrypt(
        self,
        payload: EncryptedCdekRequest,
        *,
        order_id: int,
        request_sha256: str,
        schema_version: int,
    ) -> bytes:
        key = self._keys.get(payload.key_version)
        if key is None:
            raise CdekRequestDecryptionError("CDEK request encryption key version is unavailable")
        try:
            cipher = AES.new(key, AES.MODE_GCM, nonce=_decode(payload.nonce))
            cipher.update(
                self._aad(
                    order_id=order_id,
                    request_sha256=request_sha256,
                    schema_version=schema_version,
                    key_version=payload.key_version,
                )
            )
            body = cipher.decrypt_and_verify(
                _decode(payload.ciphertext),
                _decode(payload.tag),
            )
        except (binascii.Error, ValueError) as error:
            raise CdekRequestDecryptionError("CDEK request authentication failed") from error
        if hashlib.sha256(body).hexdigest() != request_sha256:
            raise CdekRequestDecryptionError("CDEK request digest does not match plaintext")
        return body

    @staticmethod
    def _validate_context(
        body: bytes,
        *,
        order_id: int,
        request_sha256: str,
        schema_version: int,
    ) -> None:
        if not body:
            raise CdekRequestEncryptionError("CDEK request body must not be empty")
        if order_id <= 0 or schema_version <= 0:
            raise CdekRequestEncryptionError("CDEK request context is invalid")
        if hashlib.sha256(body).hexdigest() != request_sha256:
            raise CdekRequestEncryptionError("CDEK request digest does not match plaintext")

    @staticmethod
    def _aad(
        *,
        order_id: int,
        request_sha256: str,
        schema_version: int,
        key_version: int,
    ) -> bytes:
        return (
            f"garment-buro-cdek-request:order:{order_id}:request:{request_sha256}:"
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
