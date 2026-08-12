from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

from Crypto.Cipher import AES


class PayloadEncryptionError(RuntimeError):
    pass


class PayloadDecryptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EncryptedNotificationPayload:
    ciphertext: str
    nonce: str
    tag: str
    key_version: int


class NotificationPayloadCodec:
    """AES-256-GCM codec; recipient and template context never reach DB plaintext."""

    def __init__(self, keys: dict[int, bytes], *, current_version: int) -> None:
        if current_version <= 0 or current_version not in keys:
            raise ValueError("Current notification key version is missing")
        if any(version <= 0 for version in keys):
            raise ValueError("Every notification encryption key version must be positive")
        if any(len(key) != 32 for key in keys.values()):
            raise ValueError("Every notification encryption key must contain 32 bytes")
        self._keys = dict(keys)
        self.current_version = current_version

    @classmethod
    def from_base64_key(
        cls,
        encoded_key: str,
        *,
        key_version: int = 1,
    ) -> NotificationPayloadCodec:
        try:
            key = _decode(encoded_key)
        except (binascii.Error, ValueError) as error:
            raise ValueError("NOTIFICATION_ENCRYPTION_KEY must be URL-safe base64") from error
        return cls({key_version: key}, current_version=key_version)

    @classmethod
    def from_base64_keys(
        cls,
        encoded_keys: dict[int, str],
        *,
        current_version: int,
    ) -> NotificationPayloadCodec:
        try:
            keys = {version: _decode(value) for version, value in encoded_keys.items()}
        except (binascii.Error, ValueError) as error:
            raise ValueError("Notification encryption keys must be URL-safe base64") from error
        return cls(keys, current_version=current_version)

    def encrypt(self, payload: dict[str, object]) -> EncryptedNotificationPayload:
        try:
            serialized = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise PayloadEncryptionError("Notification payload is not JSON serializable") from error

        version = self.current_version
        cipher = AES.new(self._keys[version], AES.MODE_GCM)
        cipher.update(self._aad(version))
        ciphertext, tag = cipher.encrypt_and_digest(serialized)
        return EncryptedNotificationPayload(
            ciphertext=_encode(ciphertext),
            nonce=_encode(cipher.nonce),
            tag=_encode(tag),
            key_version=version,
        )

    def decrypt(self, payload: EncryptedNotificationPayload) -> dict[str, object]:
        key = self._keys.get(payload.key_version)
        if key is None:
            raise PayloadDecryptionError("Notification encryption key version is unavailable")
        try:
            cipher = AES.new(key, AES.MODE_GCM, nonce=_decode(payload.nonce))
            cipher.update(self._aad(payload.key_version))
            serialized = cipher.decrypt_and_verify(
                _decode(payload.ciphertext),
                _decode(payload.tag),
            )
            decoded = json.loads(serialized)
        except (binascii.Error, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise PayloadDecryptionError("Notification payload authentication failed") from error
        if not isinstance(decoded, dict):
            raise PayloadDecryptionError("Notification payload must be an object")
        return decoded

    @staticmethod
    def _aad(version: int) -> bytes:
        return f"garment-buro-notification:v{version}".encode("ascii")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        f"{value}{padding}",
        altchars=b"-_",
        validate=True,
    )
