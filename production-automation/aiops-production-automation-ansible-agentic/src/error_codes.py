"""Structured API error codes for programmatic consumption.

Defines stable, machine-readable error codes that clients can branch on
without parsing human-readable error messages. Error codes are immutable
once published — wording changes are safe, code values are not.

Usage:
    from src.error_codes import ApiErrorCode, error_response

    return error_response(
        code=ApiErrorCode.PAYLOAD_VALIDATION_FAILED,
        detail="labels must contain a non-empty 'alertname' field",
        status_code=400,
    )

Response format:
    {
        "code": "PAYLOAD_VALIDATION_FAILED",
        "error": "Invalid payload",
        "detail": "labels must contain a non-empty 'alertname' field",
        "retry": false
    }
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from fastapi.responses import JSONResponse


class ApiErrorCode(str, Enum):
    """Stable, machine-readable error codes for all API responses.

    These codes are part of the public API contract. Once a code is
    published, it must not be renamed or reused for a different meaning.
    Human-readable messages may change freely.

    Naming convention: UPPER_SNAKE_CASE, grouped by HTTP status code range.
    """

    # --- 400 Bad Request ---
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    PAYLOAD_VALIDATION_FAILED = "PAYLOAD_VALIDATION_FAILED"
    PAYLOAD_INVALID_JSON = "PAYLOAD_INVALID_JSON"

    # --- 401 Unauthorized ---
    UNAUTHORIZED = "UNAUTHORIZED"
    API_KEY_INVALID = "API_KEY_INVALID"
    API_KEY_MISSING = "API_KEY_MISSING"

    # --- 410 Gone ---
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_ALREADY_CONSUMED = "TOKEN_ALREADY_CONSUMED"
    TOKEN_NOT_FOUND = "TOKEN_NOT_FOUND"

    # --- 415 Unsupported Media Type ---
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"

    # --- 429 Too Many Requests ---
    RATE_LIMITED = "RATE_LIMITED"
    FLEET_BREAKER_OPEN = "FLEET_BREAKER_OPEN"
    STORM_SUPPRESSED = "STORM_SUPPRESSED"

    # --- 503 Service Unavailable ---
    SERVICE_DRAINING = "SERVICE_DRAINING"
    DEPENDENCY_UNHEALTHY = "DEPENDENCY_UNHEALTHY"

    # --- 500 Internal Server Error ---
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ENQUEUE_FAILED = "ENQUEUE_FAILED"


# Human-readable error messages for each code (can change without breaking clients)
_ERROR_MESSAGES: dict[ApiErrorCode, str] = {
    ApiErrorCode.PAYLOAD_TOO_LARGE: "Payload too large",
    ApiErrorCode.PAYLOAD_VALIDATION_FAILED: "Invalid payload",
    ApiErrorCode.PAYLOAD_INVALID_JSON: "Invalid JSON",
    ApiErrorCode.UNAUTHORIZED: "Unauthorized",
    ApiErrorCode.API_KEY_INVALID: "Invalid API key",
    ApiErrorCode.API_KEY_MISSING: "Missing API key",
    ApiErrorCode.TOKEN_EXPIRED: "Approval link expired or already used",
    ApiErrorCode.TOKEN_ALREADY_CONSUMED: "Approval link already used",
    ApiErrorCode.TOKEN_NOT_FOUND: "Approval link not found",
    ApiErrorCode.UNSUPPORTED_MEDIA_TYPE: "Unsupported Media Type",
    ApiErrorCode.RATE_LIMITED: "Rate limit exceeded",
    ApiErrorCode.FLEET_BREAKER_OPEN: "Fleet circuit breaker open",
    ApiErrorCode.STORM_SUPPRESSED: "Alert suppressed during storm",
    ApiErrorCode.SERVICE_DRAINING: "Service shutting down",
    ApiErrorCode.DEPENDENCY_UNHEALTHY: "Service dependency unhealthy",
    ApiErrorCode.INTERNAL_ERROR: "Internal server error",
    ApiErrorCode.ENQUEUE_FAILED: "Failed to enqueue alert",
}

# Whether clients should retry for each error code
_RETRYABLE: dict[ApiErrorCode, bool] = {
    ApiErrorCode.PAYLOAD_TOO_LARGE: False,
    ApiErrorCode.PAYLOAD_VALIDATION_FAILED: False,
    ApiErrorCode.PAYLOAD_INVALID_JSON: False,
    ApiErrorCode.UNAUTHORIZED: False,
    ApiErrorCode.API_KEY_INVALID: False,
    ApiErrorCode.API_KEY_MISSING: False,
    ApiErrorCode.TOKEN_EXPIRED: False,
    ApiErrorCode.TOKEN_ALREADY_CONSUMED: False,
    ApiErrorCode.TOKEN_NOT_FOUND: False,
    ApiErrorCode.UNSUPPORTED_MEDIA_TYPE: False,
    ApiErrorCode.RATE_LIMITED: True,
    ApiErrorCode.FLEET_BREAKER_OPEN: True,
    ApiErrorCode.STORM_SUPPRESSED: False,
    ApiErrorCode.SERVICE_DRAINING: True,
    ApiErrorCode.DEPENDENCY_UNHEALTHY: True,
    ApiErrorCode.INTERNAL_ERROR: True,
    ApiErrorCode.ENQUEUE_FAILED: True,
}


def error_response(
    code: ApiErrorCode,
    status_code: int,
    detail: str = "",
    retry_after_seconds: Optional[int] = None,
    extra: Optional[dict] = None,
) -> JSONResponse:
    """Build a structured error JSONResponse.

    Args:
        code: The stable error code (machine-readable).
        status_code: HTTP status code.
        detail: Additional human-readable context (optional).
        retry_after_seconds: Seconds before client should retry (optional).
        extra: Additional key-value pairs to include in the response.

    Returns:
        JSONResponse with structured error body and appropriate headers.
    """
    body: dict = {
        "code": code.value,
        "error": _ERROR_MESSAGES.get(code, code.value),
        "detail": detail or _ERROR_MESSAGES.get(code, ""),
        "retry": _RETRYABLE.get(code, False),
    }

    if retry_after_seconds is not None:
        body["retry_after_seconds"] = retry_after_seconds

    if extra:
        body.update(extra)

    headers = {}
    if retry_after_seconds is not None:
        headers["Retry-After"] = str(retry_after_seconds)

    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=headers if headers else None,
    )


def success_response(
    status_code: int = 200,
    **kwargs,
) -> JSONResponse:
    """Build a structured success JSONResponse.

    Args:
        status_code: HTTP status code (default 200).
        **kwargs: Key-value pairs to include in the response body.

    Returns:
        JSONResponse with structured success body.
    """
    return JSONResponse(status_code=status_code, content=kwargs)
