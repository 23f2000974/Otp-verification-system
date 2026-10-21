"""Unit tests for the OTP service."""

from datetime import datetime, timedelta, timezone

import pytest

from otp_core.models import ChallengeStatus
from otp_core.service import OTPService
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
verified_at: Optional[datetime] = None


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def service(clock: FakeClock) -> OTPService:
    return OTPService(
        secret=b"unit-test-secret-not-for-production",
        ttl_seconds=300,
        max_attempts=5,
        clock=clock,
    )


def test_correct_otp_verifies_once(
    service: OTPService,
) -> None:
    challenge_id, otp = service.issue("user@example.com")

    assert service.verify(
        challenge_id, "user@example.com", "login", otp
    )
    assert not service.verify(
        challenge_id, "user@example.com", "login", otp
    )

    challenge = service.get_challenge(challenge_id)
    assert challenge is not None
    assert challenge.status == ChallengeStatus.VERIFIED
    assert challenge.verified_at is not None


def test_wrong_otp_increments_attempts(
    service: OTPService,
) -> None:
    challenge_id, _ = service.issue("user@example.com")

    assert not service.verify(
        challenge_id, "user@example.com", "login", "000000"
    )

    challenge = service.get_challenge(challenge_id)
    assert challenge is not None
    assert challenge.attempts == 1
    assert challenge.status == ChallengeStatus.PENDING


def test_fifth_wrong_attempt_locks_challenge(
    service: OTPService,
) -> None:
    challenge_id, _ = service.issue("user@example.com")

    for _ in range(5):
        assert not service.verify(
            challenge_id, "user@example.com", "login", "wrong"
        )

    challenge = service.get_challenge(challenge_id)
    assert challenge is not None
    assert challenge.attempts == 5
    assert challenge.status == ChallengeStatus.LOCKED


def test_expired_otp_is_rejected(
    service: OTPService, clock: FakeClock
) -> None:
    challenge_id, otp = service.issue("user@example.com")
    clock.advance(301)

    assert not service.verify(
        challenge_id, "user@example.com", "login", otp
    )

    challenge = service.get_challenge(challenge_id)
    assert challenge is not None
    assert challenge.status == ChallengeStatus.EXPIRED


def test_otp_is_bound_to_subject_and_purpose(
    service: OTPService,
) -> None:
    challenge_id, otp = service.issue("user@example.com", "login")

    assert not service.verify(
        challenge_id, "other@example.com", "login", otp
    )
    assert not service.verify(
        challenge_id, "user@example.com", "password_reset", otp
    )
    assert service.verify(
        challenge_id, "user@example.com", "login", otp
    )


def test_unknown_challenge_is_rejected(
    service: OTPService,
) -> None:
    assert not service.verify(
        "unknown", "user@example.com", "login", "123456"
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"secret": b"", "ttl_seconds": 300, "max_attempts": 5},
        {"secret": b"secret", "ttl_seconds": 0, "max_attempts": 5},
        {"secret": b"secret", "ttl_seconds": 300, "max_attempts": 0},
    ],
)
def test_invalid_service_configuration(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        OTPService(**kwargs)
