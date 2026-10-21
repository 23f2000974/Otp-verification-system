
"""FastAPI application entry point."""

from collections.abc import Awaitable
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from otp_core.service import ChallengeCooldownError, OTPService
from pydantic import BaseModel, EmailStr, Field

from otp_api.email import (
    EmailDeliveryError,
    EmailSender,
    SMTPConfigurationError,
    SMTPEmailSender,
)
from otp_api.rate_limit import InMemoryRateLimiter, RateLimitExceeded
from otp_api.settings import Settings

_WEB_DIR = Path(__file__).parent / "static"


class IssueChallengeRequest(BaseModel):
    email: EmailStr


class IssueChallengeResponse(BaseModel):
    challenge_id: str
    expires_in_seconds: int
    retry_after_seconds: int


class VerifyChallengeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=12, pattern=r"^[0-9]+$")


class VerifyChallengeResponse(BaseModel):
    verified: bool


def create_app(
    settings: Optional[Settings] = None,
    email_sender: Optional[EmailSender] = None,
    otp_service: Optional[OTPService] = None,
) -> FastAPI:
    """Create an API instance with injectable dependencies for tests."""
    config = settings or Settings()
    service = otp_service or OTPService(
        secret=config.otp_hmac_secret.get_secret_value().encode("utf-8"),
        ttl_seconds=config.otp_ttl_seconds,
        max_attempts=config.otp_max_attempts,
        otp_length=config.otp_length,
        resend_cooldown_seconds=config.otp_resend_cooldown_seconds,
    )
    sender = email_sender or SMTPEmailSender(config)
    limiter = InMemoryRateLimiter()

    application = FastAPI(
        title=config.app_name,
        description="API for secure one-time password verification.",
        version="1.0.0",
    )
    application.state.settings = config
    application.state.otp_service = service
    application.state.email_sender = sender
    application.state.rate_limiter = limiter

    @application.middleware("http")
    async def prevent_verification_response_caching(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/challenges"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'; object-src 'none'; "
            "style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "connect-src 'self'"
        )
        return response

    application.mount(
        "/static",
        StaticFiles(directory=str(_WEB_DIR)),
        name="static",
    )

    @application.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(_WEB_DIR / "index.html")

    @application.get("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "otp-verification-platform"}

    @application.get("/api/v1/config", tags=["Verification"])
    def verification_config() -> dict[str, int]:
        return {
            "otp_length": config.otp_length,
            "ttl_seconds": config.otp_ttl_seconds,
        }

    @application.post(
        "/api/v1/challenges",
        response_model=IssueChallengeResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["Verification"],
    )
    def issue_challenge(
        payload: IssueChallengeRequest,
        request: Request,
    ) -> IssueChallengeResponse:
        _check_rate_limit(request, "issue", 5, 60)
        normalized_email = str(payload.email)
        try:
            challenge_id, otp = service.issue(normalized_email, "login")
        except ChallengeCooldownError as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another code.",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error

        try:
            sender.send_otp(
                normalized_email,
                otp,
                config.otp_ttl_seconds,
            )
        except SMTPConfigurationError as error:
            service.cancel(challenge_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is not configured.",
            ) from error
        except EmailDeliveryError as error:
            service.cancel(challenge_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The verification email could not be sent.",
            ) from error

        return IssueChallengeResponse(
            challenge_id=challenge_id,
            expires_in_seconds=config.otp_ttl_seconds,
            retry_after_seconds=config.otp_resend_cooldown_seconds,
        )

    @application.post(
        "/api/v1/challenges/{challenge_id}/verify",
        response_model=VerifyChallengeResponse,
        tags=["Verification"],
    )
    def verify_challenge(
        challenge_id: str,
        payload: VerifyChallengeRequest,
        request: Request,
    ) -> VerifyChallengeResponse:
        _check_rate_limit(request, "verify", 20, 60)
        if len(payload.code) != config.otp_length:
            raise HTTPException(
                status_code=422,
                detail=f"Code must contain exactly {config.otp_length} digits.",
            )
        verified = service.verify(
            challenge_id,
            str(payload.email),
            "login",
            payload.code,
        )
        if not verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The code is invalid, expired, or already used.",
            )
        return VerifyChallengeResponse(verified=True)

    def _check_rate_limit(
        request: Request,
        action: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        client_address = (
            request.client.host if request.client is not None else "unknown"
        )
        try:
            limiter.check((action, client_address), limit, window_seconds)
        except RateLimitExceeded as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error

    return application


app = create_app()
