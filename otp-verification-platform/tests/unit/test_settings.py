"""Unit tests for application configuration validation."""

import pytest
from otp_api.settings import Settings
from pydantic import ValidationError


def test_production_requires_custom_secret_and_smtp_host() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production")


def test_production_accepts_explicit_secret_and_smtp_host() -> None:
    settings = Settings(
        app_env="production",
        otp_hmac_secret="a-unique-production-secret-with-more-than-32-bytes",
        smtp_host="mail.example.com",
    )

    assert settings.app_env == "production"
    assert settings.smtp_host == "mail.example.com"


@pytest.mark.parametrize(
    "settings",
    [
        {"otp_hmac_secret": "short"},
        {"smtp_username": "mailer"},
        {"smtp_password": "password"},
        {"smtp_port": 65536},
        {"otp_length": 13},
    ],
)
def test_invalid_settings_are_rejected(settings: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(**settings)
