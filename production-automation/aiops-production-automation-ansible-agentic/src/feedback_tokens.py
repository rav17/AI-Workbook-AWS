"""Signed, expiring tokens for the "did this advice help?" links in advisory emails.

A token carries the incident id, the verdict the link records (``success`` or
``failure``) and an expiry time, signed with HMAC-SHA256 using the same secret as
the approval links. The token itself is stateless. Single use is enforced where the
outcome is written: ``IncidentMemoryStore.record_outcome(only_if_pending=True)`` applies
only while the incident outcome is still ``pending``, so the first answer wins.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

VERDICT_SUCCESS = "success"
VERDICT_FAILURE = "failure"
VALID_VERDICTS = frozenset({VERDICT_SUCCESS, VERDICT_FAILURE})

# Operators may read the email days later; the incident record itself lives 90 days.
DEFAULT_TOKEN_TTL_SECONDS = 7 * 24 * 3600


@dataclass(frozen=True)
class FeedbackClaims:
    """Verified contents of a feedback token.

    Attributes:
        incident_id: The incident the feedback is about.
        verdict: ``success`` or ``failure``.
        expires_at: Unix time after which the token is no longer valid.
    """

    incident_id: str
    verdict: str
    expires_at: int


def _b64encode(raw: bytes) -> str:
    """Encode bytes as unpadded URL-safe base64."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    """Decode unpadded URL-safe base64.

    Raises:
        ValueError: If the value is not valid base64.
    """
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (binascii.Error, ValueError) as e:
        raise ValueError("invalid base64") from e


def _sign(secret: str, payload_b64: str) -> str:
    """Return the URL-safe HMAC-SHA256 signature of an encoded payload."""
    digest = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    )
    return _b64encode(digest.digest())


def create_feedback_token(
    incident_id: str,
    verdict: str,
    secret: str,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    now: Optional[float] = None,
) -> str:
    """Create a signed feedback token.

    Args:
        incident_id: The incident the feedback is about.
        verdict: ``success`` or ``failure``.
        secret: HMAC signing secret.
        ttl_seconds: Token lifetime in seconds.
        now: Current Unix time (injectable for tests).

    Returns:
        A URL-safe token string.

    Raises:
        ValueError: If the verdict is not valid or the incident id or secret is empty.
    """
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VALID_VERDICTS)}")
    if not incident_id or not secret:
        raise ValueError("incident_id and secret are required")
    issued = time.time() if now is None else now
    claims = {"i": incident_id, "v": verdict, "e": int(issued) + ttl_seconds}
    payload_b64 = _b64encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(secret, payload_b64)}"


def verify_feedback_token(
    token: str, secret: str, now: Optional[float] = None
) -> Optional[FeedbackClaims]:
    """Verify a feedback token.

    Args:
        token: The token from the link.
        secret: HMAC signing secret.
        now: Current Unix time (injectable for tests).

    Returns:
        The claims if the signature is valid and the token has not expired,
        otherwise None.
    """
    if not token or not secret or token.count(".") != 1:
        return None
    payload_b64, signature = token.split(".")
    if not hmac.compare_digest(_sign(secret, payload_b64), signature):
        return None
    try:
        claims = json.loads(_b64decode(payload_b64))
        incident_id = claims["i"]
        verdict = claims["v"]
        expires_at = int(claims["e"])
    except (ValueError, KeyError, TypeError):
        return None
    if (
        not isinstance(incident_id, str)
        or not incident_id
        or verdict not in VALID_VERDICTS
    ):
        return None
    current = time.time() if now is None else now
    if current > expires_at:
        return None
    return FeedbackClaims(
        incident_id=incident_id, verdict=verdict, expires_at=expires_at
    )
