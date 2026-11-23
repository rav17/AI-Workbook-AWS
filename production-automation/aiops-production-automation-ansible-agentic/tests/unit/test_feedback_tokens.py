"""Unit tests for signed advisory feedback tokens."""

from __future__ import annotations

import pytest

from src.feedback_tokens import (
    VERDICT_FAILURE,
    VERDICT_SUCCESS,
    create_feedback_token,
    verify_feedback_token,
)

pytestmark = pytest.mark.unit

SECRET = "test-secret"  # noqa: S105 - test-only value


def test_round_trip() -> None:
    token = create_feedback_token(
        "inc-1", VERDICT_SUCCESS, SECRET, ttl_seconds=60, now=1000
    )
    claims = verify_feedback_token(token, SECRET, now=1030)
    assert claims is not None
    assert (claims.incident_id, claims.verdict, claims.expires_at) == (
        "inc-1",
        VERDICT_SUCCESS,
        1060,
    )


def test_token_is_url_safe() -> None:
    token = create_feedback_token("inc/with?odd&chars", VERDICT_FAILURE, SECRET)
    assert all(c.isalnum() or c in "-_." for c in token)


def test_expired_token_is_rejected() -> None:
    token = create_feedback_token(
        "inc-1", VERDICT_SUCCESS, SECRET, ttl_seconds=60, now=1000
    )
    assert verify_feedback_token(token, SECRET, now=1061) is None


def test_wrong_secret_is_rejected() -> None:
    token = create_feedback_token("inc-1", VERDICT_SUCCESS, SECRET)
    assert verify_feedback_token(token, "other-secret") is None


def test_tampered_payload_is_rejected() -> None:
    good = create_feedback_token("inc-1", VERDICT_SUCCESS, SECRET)
    other = create_feedback_token("inc-1", VERDICT_FAILURE, SECRET)
    # Swap in the payload of a different verdict while keeping the first signature.
    forged = f"{other.split('.')[0]}.{good.split('.')[1]}"
    assert verify_feedback_token(forged, SECRET) is None


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "!!!.???"])
def test_malformed_tokens_are_rejected(token: str) -> None:
    assert verify_feedback_token(token, SECRET) is None


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        create_feedback_token("inc-1", "maybe", SECRET)
    with pytest.raises(ValueError):
        create_feedback_token("", VERDICT_SUCCESS, SECRET)
    with pytest.raises(ValueError):
        create_feedback_token("inc-1", VERDICT_SUCCESS, "")
