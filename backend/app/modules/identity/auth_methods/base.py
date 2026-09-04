from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AuthMethodDescriptor:
    code: str
    kind: str
    enabled: bool
    reason: str | None = None


class AuthMethod(Protocol):
    @property
    def descriptor(self) -> AuthMethodDescriptor: ...
