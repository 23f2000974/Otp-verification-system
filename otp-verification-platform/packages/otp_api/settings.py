"""Environment-backed application settings."""

from typing import Literal, Optional

from pydantic import EmailStr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEVELOPMENT_SECRET = "local-development-secret-never-use-in-production"


class Settings(BaseSettings):
    """Configuration shared by the API and its delivery adapter."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        validate_default=True,
    )

    app_name: str = "OTP Verification Platform"
    app_env: Literal["development", "test", "production"] = "development"
    otp_hmac_secret: SecretStr = SecretStr(_DEVELOPMENT_SECRET)
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_length: int = 6
    otp_resend_cooldown_seconds: int = 60
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[SecretStr] = None
    smtp_from_email: EmailStr = "no-reply@example.com"
    smtp_timeout_seconds: float = 10.0

    @field_validator("otp_hmac_secret")
    @classmethod
    def validate_hmac_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("OTP_HMAC_SECRET must be at least 32 bytes")
        return value

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if not 6 <= self.otp_length <= 12:
            raise ValueError("OTP_LENGTH must be between 6 and 12")
        if self.otp_ttl_seconds <= 0:
            raise ValueError("OTP_TTL_SECONDS must be positive")
        if self.otp_max_attempts <= 0:
            raise ValueError("OTP_MAX_ATTEMPTS must be positive")
        if self.otp_resend_cooldown_seconds < 0:
            raise ValueError("OTP_RESEND_COOLDOWN_SECONDS must not be negative")
        if not 1 <= self.smtp_port <= 65535:
            raise ValueError("SMTP_PORT must be between 1 and 65535")
        if self.smtp_timeout_seconds <= 0:
            raise ValueError("SMTP_TIMEOUT_SECONDS must be positive")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")

        if self.app_env == "production":
            if self.otp_hmac_secret.get_secret_value() == _DEVELOPMENT_SECRET:
                raise ValueError("Set a unique OTP_HMAC_SECRET in production")
            if not self.smtp_host:
                raise ValueError("SMTP_HOST is required in production")
        return self
