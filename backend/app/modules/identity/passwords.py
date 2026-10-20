from __future__ import annotations

from anyio import CapacityLimiter, to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type


class PasswordSecurity:
    """Argon2id password hashing with a timing-safe missing-user verification path."""

    algorithm = "argon2id"

    def __init__(self) -> None:
        self._limiter = CapacityLimiter(2)
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash("garment-buro-dummy-password-value")

    async def hash(self, password: str) -> str:
        return await to_thread.run_sync(self._hasher.hash, password, limiter=self._limiter)

    async def verify(self, password_hash: str, password: str) -> bool:
        try:
            return await to_thread.run_sync(
                self._hasher.verify, password_hash, password, limiter=self._limiter
            )
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    async def verify_missing_user(self, password: str) -> None:
        await self.verify(self._dummy_hash, password)

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True
