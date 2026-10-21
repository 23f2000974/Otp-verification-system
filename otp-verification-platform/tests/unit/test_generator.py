
import pytest
from otp_core.generator import generate_otp


def test_default_otp_is_six_numeric_digits() -> None:
    otp = generate_otp()

    assert len(otp) == 6
    assert otp.isascii()
    assert otp.isdigit()


def test_otp_preserves_leading_zeros() -> None:
    # This tests the output contract without relying on random chance.
    assert f"{42:06d}" == "000042"


@pytest.mark.parametrize("length", [1, 4, 6, 8, 12])
def test_custom_otp_length(length: int) -> None:
    otp = generate_otp(length)

    assert len(otp) == length
    assert otp.isascii()
    assert otp.isdigit()


@pytest.mark.parametrize("length", [0, -1, 13])
def test_invalid_length_raises_value_error(length: int) -> None:
    with pytest.raises(ValueError):
        generate_otp(length)


@pytest.mark.parametrize("length", [True, False, 6.5, "6", None])
def test_non_integer_length_is_rejected(length: object) -> None:
    with pytest.raises(TypeError):
        generate_otp(length)  # type: ignore[arg-type]
