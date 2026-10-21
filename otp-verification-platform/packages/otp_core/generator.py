
"""Cryptographically secure one-time password generation."""

import secrets


def generate_otp(length: int = 6) -> str:
    """Generate a zero-padded numeric OTP.

    Args:
        length: Number of decimal digits, between 1 and 12.

    Returns:
        A numeric string with exactly `length` characters.
    """
    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length must be an integer")

    if not 1 <= length <= 12:
        raise ValueError("length must be between 1 and 12")

    return f"{secrets.randbelow(10**length):0{length}d}"
