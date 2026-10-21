
"""FastAPI application entry point."""
from fastapi import FastAPI

app = FastAPI(
    title="OTP Verification Platform",
    description="API for secure one-time password verification.",
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Report whether the API process is responding."""
    return {
        "status": "ok",
        "service": "otp-verification-platform",
    }
