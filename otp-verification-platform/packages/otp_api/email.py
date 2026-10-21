"""SMTP-based delivery of verification codes."""

import smtplib
import ssl
from email.message import EmailMessage
from math import ceil
from typing import Protocol

from otp_api.settings import Settings


class EmailDeliveryError(Exception):
    """Raised when a verification email cannot be delivered."""


class SMTPConfigurationError(EmailDeliveryError):
    """Raised when SMTP delivery has not been configured."""


class EmailSender(Protocol):
    def send_otp(self, recipient: str, otp: str, ttl_seconds: int) -> None:
        """Deliver a one-time password without exposing it to the API client."""


class SMTPEmailSender:
    """Send verification mail through an SMTP server using STARTTLS."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send_otp(self, recipient: str, otp: str, ttl_seconds: int) -> None:
        if not self._settings.smtp_host:
            raise SMTPConfigurationError("SMTP_HOST is not configured")

        message = EmailMessage()
        message["Subject"] = "Your verification code"
        message["From"] = str(self._settings.smtp_from_email)
        message["To"] = recipient
        minutes = max(1, ceil(ttl_seconds / 60))
        minute_label = "minute" if minutes == 1 else "minutes"
        message.set_content(
            "Your one-time verification code is "
            f"{otp}.\n\nIt expires in {minutes} {minute_label}. "
            "If you did not request this code, you can ignore this email."
        )

        try:
            with smtplib.SMTP(
                self._settings.smtp_host,
                self._settings.smtp_port,
                timeout=self._settings.smtp_timeout_seconds,
            ) as client:
                client.ehlo()
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
                if self._settings.smtp_username and self._settings.smtp_password:
                    client.login(
                        self._settings.smtp_username,
                        self._settings.smtp_password.get_secret_value(),
                    )
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise EmailDeliveryError("SMTP delivery failed") from error
