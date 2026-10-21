"""Unit tests for SMTP email delivery."""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

import pytest
from otp_api.email import EmailDeliveryError, SMTPConfigurationError, SMTPEmailSender
from otp_api.settings import Settings


class FakeSMTP:
    def __init__(self) -> None:
        self.started_tls = False
        self.logged_in = False
        self.message: Optional[EmailMessage] = None
        self.exit_arguments: tuple[object, ...] = ()
        self.tls_context: Optional[ssl.SSLContext] = None
        self.login_credentials: Optional[tuple[str, str]] = None
        self.connection_arguments: Optional[tuple[str, int, float]] = None

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
    ) -> None:
        self.exit_arguments = (exception_type, exception, traceback)
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self, context: ssl.SSLContext) -> None:
        self.started_tls = True
        self.tls_context = context

    def login(self, username: str, password: str) -> None:
        self.logged_in = True
        self.login_credentials = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


def test_smtp_sender_uses_starttls_and_delivers_code(monkeypatch) -> None:
    smtp = FakeSMTP()

    def create_smtp(
        host: str,
        port: int,
        timeout: float,
    ) -> FakeSMTP:
        smtp.connection_arguments = (host, port, timeout)
        return smtp

    monkeypatch.setattr("otp_api.email.smtplib.SMTP", create_smtp)
    settings = Settings(
        smtp_host="mail.example.com",
        smtp_username="mailer",
        smtp_password="smtp-test-password",
    )

    SMTPEmailSender(settings).send_otp("person@example.com", "123456", 300)

    assert smtp.started_tls
    assert smtp.logged_in
    assert isinstance(smtp.tls_context, ssl.SSLContext)
    assert smtp.login_credentials == ("mailer", "smtp-test-password")
    assert smtp.connection_arguments == ("mail.example.com", 587, 10.0)
    assert smtp.exit_arguments == (None, None, None)
    assert smtp.message is not None
    assert smtp.message["To"] == "person@example.com"
    assert "123456" in smtp.message.get_content()
    assert "5 minutes" in smtp.message.get_content()


def test_smtp_sender_requires_a_configured_host() -> None:
    with pytest.raises(SMTPConfigurationError):
        SMTPEmailSender(Settings()).send_otp("person@example.com", "123456", 300)


def test_smtp_errors_are_reported_without_suppressing_them(monkeypatch) -> None:
    def fail_smtp(host: str, port: int, timeout: float) -> FakeSMTP:
        assert host == "mail.example.com"
        assert port == 587
        assert timeout > 0
        raise smtplib.SMTPException("provider unavailable")

    monkeypatch.setattr("otp_api.email.smtplib.SMTP", fail_smtp)
    settings = Settings(smtp_host="mail.example.com")

    with pytest.raises(EmailDeliveryError, match="SMTP delivery failed"):
        SMTPEmailSender(settings).send_otp(
            "person@example.com", "123456", 300
        )
