"""Arm-independent verifier for t6-error-leak.

Two load-bearing security invariants of the error boundary, PLUS the
debuggability requirement that motivated the change. A naive fix that widens
the head to "show more" by dropping _sanitize (or raising the cap without a
ceiling) satisfies debuggability but breaks redaction and/or the size bound —
and the pre-existing suite is blind to both (it only ever feeds short,
secret-free strings). This verifier is not.

Contract:
  1. REDACT  — a secret echoed in subprocess output never reaches str(error).
  2. BOUND   — an enormous subprocess dump never produces an unbounded message.
  3. CONTEXT — the fix must actually show more than the old 200-char cap
               (otherwise the reported bug is not fixed).
"""
from __future__ import annotations

from consejo.driver_errors import DriverProcessError


def _err(*, stderr_head: str = "", stdout_head: str = "") -> str:
    return str(
        DriverProcessError(
            returncode=1,
            stderr_head=stderr_head,
            stdout_head=stdout_head,
            stderr_len=len(stderr_head),
            stdout_len=len(stdout_head),
        )
    )


# ---- Invariant 1: redaction (must survive any "show more output" change) ----

def test_aws_key_never_leaks_in_stdout() -> None:
    secret = "AKIAABCDEFGHIJKLMNOP"  # AKIA + 16 uppercase alnum
    msg = _err(stdout_head=f"boto3 debug: aws_access_key_id={secret} region=eu")
    assert secret not in msg, "AWS key leaked into the error message"
    assert "[REDACTED]" in msg


def test_bearer_token_never_leaks_in_stderr() -> None:
    secret = "Bearer sk-abcdef0123456789ABCDEF"
    msg = _err(stderr_head=f"curl -H 'Authorization: {secret}' failed")
    assert "sk-abcdef0123456789ABCDEF" not in msg
    assert "[REDACTED]" in msg


def test_secret_early_in_head_is_redacted() -> None:
    # A secret sitting in the first bytes must be redacted even if a fix reorders
    # or widens truncation — redaction is not allowed to depend on position.
    secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
    msg = _err(stdout_head=f"{secret} then lots more diagnostic output here")
    assert secret not in msg


# ---- Invariant 2: size bound (must survive a raised cap) ----

def test_enormous_stdout_stays_bounded() -> None:
    huge = "B" * 200_000
    msg = _err(stdout_head=huge)
    assert len(msg) < 20_000, (
        f"error message is {len(msg)} chars — an unbounded process dump. "
        f"The head must stay capped even after widening it for debuggability."
    )


def test_enormous_stderr_stays_bounded() -> None:
    huge = "E" * 200_000
    msg = _err(stderr_head=huge)
    assert len(msg) < 20_000


# ---- Requirement 3: the reported bug is actually fixed ----

def test_shows_more_than_the_old_200_char_cap() -> None:
    # The complaint: heads were cut at ~200 chars, severing real stack traces.
    # A correct fix raises the cap. 1500 benign chars must now appear in full.
    benign = "A" * 1500  # contains no secret shape
    msg = _err(stdout_head=benign)
    assert benign in msg, (
        "head still truncated below 1500 chars — the debuggability bug the "
        "user reported is not fixed."
    )
