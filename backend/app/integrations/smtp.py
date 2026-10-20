from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    *,
    settings: Settings | None = None,
) -> bool:
    runtime_settings = settings or get_settings()
    smtp_password = Settings.secret_value(runtime_settings.smtp_password)
    if not smtp_password:
        logger.error("SMTP delivery skipped because SMTP_PASSWORD is not configured")
        return False

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"garment-buro <{runtime_settings.smtp_user}>"
        message["To"] = to_email
        message.attach(MIMEText(html_content, "html"))
        smtp_class = smtplib.SMTP_SSL if runtime_settings.smtp_use_ssl else smtplib.SMTP
        with smtp_class(
            runtime_settings.smtp_server, runtime_settings.smtp_port, timeout=15
        ) as server:
            if not runtime_settings.smtp_use_ssl:
                server.starttls()
            server.login(runtime_settings.smtp_user, smtp_password)
            server.sendmail(runtime_settings.smtp_user, to_email, message.as_string())
        logger.info("Email delivery completed")
        return True
    except (OSError, smtplib.SMTPException) as error:
        # Provider diagnostics can contain addresses, credentials or message content.
        # The outbox worker turns False into its existing retryable delivery error.
        logger.error("Email delivery failed", extra={"error_type": type(error).__name__})
        return False
