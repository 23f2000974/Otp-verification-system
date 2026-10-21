

"""Application service for issuing and verifying OTP challenges."""

import secrets
from datetime import datetime, timedelta, timezone
from math import ceil
from threading import RLock
from typing import Callable, Optional

from otp_core.generator import generate_otp
from otp_core.models import ChallengeStatus, OTPChallenge
from otp_core.security import digest_otp, verify_digest


class ChallengeCooldownError(ValueError):
    """Raised when a subject requests a challenge before its cooldown ends."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("A verification code was requested too recently")



class OTPService:
    """In-memory OTP service for development and unit testing.

    This implementation is not production storage. Use a persistent
    store with atomic state transitions before deploying multiple workers.
    """

    def __init__(
        self,
        secret: bytes,
        ttl_seconds: int = 300,
        max_attempts: int = 5,
        otp_length: int = 6,
        resend_cooldown_seconds: int = 60,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if not secret:
            raise ValueError("secret must not be empty")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if not 6 <= otp_length <= 12:
            raise ValueError("otp_length must be between 6 and 12")
        if resend_cooldown_seconds < 0:
            raise ValueError("resend_cooldown_seconds must not be negative")

        self._secret = secret
        self._ttl_seconds = ttl_seconds
        self._max_attempts = max_attempts
        self._otp_length = otp_length
        self._resend_cooldown_seconds = resend_cooldown_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._challenges: dict[str, OTPChallenge] = {}
        self._last_issued: dict[tuple[str, str], datetime] = {}
        self._subject_challenges: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def issue(
        self, subject: str, purpose: str = "login"
    ) -> tuple[str, str]:
        """Create a challenge and return its ID and OTP.

        The returned OTP is intended for the delivery adapter only.
        Never expose it in a production API response or log.
        """
        if not subject or not subject.strip():
            raise ValueError("subject must not be empty")
        if not purpose or not purpose.strip():
            raise ValueError("purpose must not be empty")

        with self._lock:
            now = self._clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("clock must return a timezone-aware datetime")

            subject_key = (subject, purpose)
            last_issued = self._last_issued.get(subject_key)
            if last_issued is not None:
                elapsed = (now - last_issued).total_seconds()
                if elapsed < self._resend_cooldown_seconds:
                    raise ChallengeCooldownError(
                        ceil(self._resend_cooldown_seconds - elapsed)
                    )

            previous_id = self._subject_challenges.get(subject_key)
            if previous_id is not None:
                previous = self._challenges.get(previous_id)
                if previous is not None and previous.status == ChallengeStatus.PENDING:
                    previous.status = ChallengeStatus.EXPIRED

            challenge_id = secrets.token_urlsafe(24)
            otp = generate_otp(self._otp_length)
            challenge = OTPChallenge(
                challenge_id=challenge_id,
                subject=subject,
                purpose=purpose,
                digest=digest_otp(
                    self._secret, challenge_id, subject, purpose, otp
                ),
                created_at=now,
                expires_at=now + timedelta(seconds=self._ttl_seconds),
                max_attempts=self._max_attempts,
            )

            self._challenges[challenge_id] = challenge
            self._last_issued[subject_key] = now
            self._subject_challenges[subject_key] = challenge_id
            return challenge_id, otp

    def verify(
        self,
        challenge_id: str,
        subject: str,
        purpose: str,
        otp: str,
    ) -> bool:
        """Verify a code, allowing each challenge to succeed only once."""
        with self._lock:
            challenge = self._challenges.get(challenge_id)
            if challenge is None:
                return False

            if challenge.status != ChallengeStatus.PENDING:
                return False

            now = self._clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("clock must return a timezone-aware datetime")
            if now >= challenge.expires_at:
                challenge.status = ChallengeStatus.EXPIRED
                return False

            if challenge.attempts >= challenge.max_attempts:
                challenge.status = ChallengeStatus.LOCKED
                return False

            candidate = digest_otp(
                self._secret, challenge_id, subject, purpose, otp
            )

            if verify_digest(challenge.digest, candidate):
                challenge.status = ChallengeStatus.VERIFIED
                challenge.verified_at = now
                return True

            challenge.attempts += 1
            if challenge.attempts >= challenge.max_attempts:
                challenge.status = ChallengeStatus.LOCKED
            return False

    def cancel(self, challenge_id: str) -> None:
        """Invalidate a pending challenge after its delivery fails."""
        with self._lock:
            challenge = self._challenges.get(challenge_id)
            if challenge is not None and challenge.status == ChallengeStatus.PENDING:
                challenge.status = ChallengeStatus.EXPIRED
                subject_key = (challenge.subject, challenge.purpose)
                if self._subject_challenges.get(subject_key) == challenge_id:
                    self._subject_challenges.pop(subject_key, None)
                    self._last_issued.pop(subject_key, None)

    def get_challenge(
        self, challenge_id: str
    ) -> Optional[OTPChallenge]:
        """Return internal challenge state for tests and development."""
        with self._lock:
            return self._challenges.get(challenge_id)
