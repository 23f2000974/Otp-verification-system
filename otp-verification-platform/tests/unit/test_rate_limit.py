"""Unit tests for the in-process request limiter."""

import otp_api.rate_limit as rate_limit
import pytest
from otp_api.rate_limit import InMemoryRateLimiter, RateLimitExceeded


def test_fixed_window_rejects_requests_after_the_limit(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr(rate_limit, "monotonic", lambda: now)
    limiter = InMemoryRateLimiter()

    limiter.check(("issue", "127.0.0.1"), limit=1, window_seconds=60)
    with pytest.raises(RateLimitExceeded) as error:
        limiter.check(("issue", "127.0.0.1"), limit=1, window_seconds=60)

    assert error.value.retry_after_seconds == 60


def test_fixed_window_resets_after_its_duration(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr(rate_limit, "monotonic", lambda: now)
    limiter = InMemoryRateLimiter()
    limiter.check(("verify", "127.0.0.1"), limit=1, window_seconds=60)

    now += 60
    limiter.check(("verify", "127.0.0.1"), limit=1, window_seconds=60)
