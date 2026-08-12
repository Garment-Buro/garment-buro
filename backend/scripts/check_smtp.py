"""Manual SMTP connectivity check; this file is not part of the test suite."""

import smtplib
import ssl

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError

SETTINGS = get_settings()


def check_ssl_port() -> bool:
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            SETTINGS.smtp_server,
            465,
            timeout=20,
            context=context,
        ) as server:
            server.ehlo()
            server.login(
                SETTINGS.smtp_user,
                SETTINGS.require_secret("smtp_password", "SMTP_PASSWORD"),
            )
        print("SMTP 465 SSL: OK")
        return True
    except (ConfigurationError, OSError, smtplib.SMTPException) as error:
        print(f"SMTP 465 SSL: {type(error).__name__}")
        return False


def check_starttls_port() -> bool:
    try:
        with smtplib.SMTP(SETTINGS.smtp_server, 587, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(
                SETTINGS.smtp_user,
                SETTINGS.require_secret("smtp_password", "SMTP_PASSWORD"),
            )
        print("SMTP 587 STARTTLS: OK")
        return True
    except (ConfigurationError, OSError, smtplib.SMTPException) as error:
        print(f"SMTP 587 STARTTLS: {type(error).__name__}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if (check_ssl_port() or check_starttls_port()) else 1)
