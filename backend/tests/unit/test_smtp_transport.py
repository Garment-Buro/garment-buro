from __future__ import annotations

import logging
import smtplib
from email import message_from_string

import pytest

from app.core.config import AppEnvironment, Settings
from app.integrations import smtp


def settings(use_ssl):
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        smtp_server="smtp.example.test",
        smtp_port=465 if use_ssl else 587,
        smtp_user="sender@example.test",
        smtp_password="fixture-password",
        smtp_use_ssl=use_ssl,
    )


@pytest.mark.parametrize("use_ssl", [True, False])
def test_smtp_sends_utf8_html_with_configured_tls_and_envelope(monkeypatch, use_ssl):
    calls = []

    class Server:
        def __init__(self, host, port, **kwargs):
            calls.append(("connect", host, port, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            calls.append(("close",))

        def starttls(self):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def sendmail(self, sender, recipient, message):
            calls.append(("send", sender, recipient, message))

    monkeypatch.setattr(smtp.smtplib, "SMTP_SSL" if use_ssl else "SMTP", Server)
    assert (
        smtp.send_email(
            "recipient@example.test", "Подтверждение", "<p>Письмо</p>", settings=settings(use_ssl)
        )
        is True
    )
    assert calls[0] == ("connect", "smtp.example.test", 465 if use_ssl else 587, {"timeout": 15})
    assert ("starttls",) in calls if not use_ssl else ("starttls",) not in calls
    assert ("login", "sender@example.test", "fixture-password") in calls
    send = next(row for row in calls if row[0] == "send")
    assert send[1:3] == ("sender@example.test", "recipient@example.test")
    message = message_from_string(send[3])
    html = message.get_payload(0)
    assert html.get_content_type() == "text/html"
    assert html.get_payload(decode=True).decode(html.get_content_charset()) == "<p>Письмо</p>"
    assert calls[-1] == ("close",)


def test_smtp_failure_is_retryable_without_raw_provider_diagnostics_in_logs(monkeypatch, caplog):
    class Server:
        def __init__(self, *_args, **_kwargs):
            raise smtplib.SMTPAuthenticationError(535, b"sensitive-smtp-diagnostic")

    monkeypatch.setattr(smtp.smtplib, "SMTP_SSL", Server)
    with caplog.at_level(logging.ERROR):
        assert (
            smtp.send_email(
                "recipient@example.test", "Subject", "<p>Body</p>", settings=settings(True)
            )
            is False
        )
    assert "Email delivery failed" in caplog.text
    assert "sensitive-smtp-diagnostic" not in caplog.text
    assert "fixture-password" not in caplog.text
    assert "recipient@example.test" not in caplog.text


def test_smtp_without_password_fails_before_connecting(monkeypatch):
    def reject_connection(*_args, **_kwargs):
        raise AssertionError("Missing credentials must not open an SMTP connection")

    monkeypatch.setattr(smtp.smtplib, "SMTP_SSL", reject_connection)
    configuration = settings(True).model_copy(update={"smtp_password": None})
    assert (
        smtp.send_email("recipient@example.test", "Subject", "Body", settings=configuration)
        is False
    )
