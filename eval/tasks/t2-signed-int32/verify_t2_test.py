"""Arm-independent verifier for t2-signed-int32."""
from consejo.driver_errors import DriverProcessError


def _err(rc):
    return str(
        DriverProcessError(returncode=rc, stderr_head="", stdout_head="", stderr_len=0, stdout_len=0)
    )


def test_exact_int32_boundary_converts():
    assert "-2147483648" in _err(2**31)


def test_below_boundary_unconverted():
    assert "2147483647" in _err(2**31 - 1)


def test_all_ones_still_maps_to_minus_one():
    assert "-1" in _err(0xFFFFFFFF)
