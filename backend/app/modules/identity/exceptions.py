from __future__ import annotations


class IdentityError(RuntimeError):
    """Base error safe for translation at the HTTP boundary."""


class InvalidEmailError(IdentityError):
    pass


class EmailAlreadyUsedError(IdentityError):
    pass


class OtpRateLimitError(IdentityError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("OTP request rate limit exceeded")
        self.retry_after_seconds = max(1, retry_after_seconds)


class InvalidOtpError(IdentityError):
    pass


class ExpiredOtpError(IdentityError):
    pass


class InvalidSessionError(IdentityError):
    pass


class RefreshTokenReuseError(InvalidSessionError):
    pass


class InactiveUserError(IdentityError):
    pass


class PermissionDeniedError(IdentityError):
    pass
