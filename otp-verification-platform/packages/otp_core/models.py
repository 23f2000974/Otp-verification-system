
"""Domain models for OTP challenges."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ChallengeStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    LOCKED = "locked"


@dataclass
class OTPChallenge:
    challenge_id: str
    subject: str
    purpose: str
    digest: str
    created_at: datetime
    expires_at: datetime
    max_attempts: int
    attempts: int = 0
    status: ChallengeStatus = ChallengeStatus.PENDING
    verified_at: Optional[datetime] = None
