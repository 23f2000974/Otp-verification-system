
"""Unit tests for OTP security helpers."""

import pytest
from otp_core.security import digest_otp, verify_digest


def test_same_inputs_produce_same_digest() -> None:
    first = digest_otp(
        b"test-secret", "challenge-1", "user@example.com", "login", "123456"
    )
    second = digest_otp(
        b"test-secret", "challenge-1", "user@example.com", "login", "123456"
    )

    assert first == second


def test_different_challenges_produce_different_digests() -> None:
    first = digest_otp(
        b"test-secret", "challenge-1", "user@example.com", "login", "123456"
    )
    second = digest_otp(
        b"test-secret", "challenge-2", "user@example.com", "login", "123456"
    )

    assert first != second


def test_digest_is_bound_to_subject_and_purpose() -> None:
    expected = digest_otp(
        b"test-secret", "challenge-1", "user@example.com", "login", "123456"
    )
    wrong_subject = digest_otp(
        b"test-secret", "challenge-1", "other@example.com", "login", "123456"
    )
    wrong_purpose = digest_otp(
        b"test-secret", "challenge-1", "user@example.com", "signup", "123456"
    )

    assert not verify_digest(expected, wrong_subject)
    assert not verify_digest(expected, wrong_purpose)


def test_empty_secret_is_rejected() -> None:
    with pytest.raises(ValueError):
        digest_otp(b"", "challenge-1", "user@example.com", "login", "123456")
