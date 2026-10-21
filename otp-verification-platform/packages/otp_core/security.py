
"""Security helpers for OTP verification."""

import hashlib
import hmac


def digest_otp(
    secret: bytes,
    challenge_id: str,
    subject: str,
    purpose: str,
    otp: str,
) -> str:
    """Create a keyed digest bound to a challenge, subject, and purpose."""
    if not secret:
        raise ValueError("The OTP HMAC secret must not be empty")

    message = "\0".join(
        ("otp-v1", challenge_id, subject, purpose, otp)
    ).encode("utf-8")

    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_digest(expected: str, candidate: str) -> bool:
    """Compare digest strings using constant-time comparison."""
    return hmac.compare_digest(expected, candidate)
