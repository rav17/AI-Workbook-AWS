"""Structured audit logging to CloudWatch with PII hashing."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger("fpl.audit")


class AuditLogger:
    """Structured audit logging with PII protection per NFR-3 AC4."""

    def __init__(self, log_group: str, agent_name: str):
        self._log_group = log_group
        self._agent_name = agent_name
        self._tz = ZoneInfo("America/New_York")
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    @staticmethod
    def _hash_pii(value: str) -> str:
        return f"sha256:{hashlib.sha256(value.encode()).hexdigest()[:16]}"

    @staticmethod
    def _mask_phone(phone: str) -> str:
        if len(phone) >= 4:
            return f"***{phone[-4:]}"
        return "****"

    def _sanitize(self, details: dict[str, Any], pii_fields: list[str] | None = None) -> dict[str, Any]:
        """Hash PII fields and mask phone numbers in log output."""
        sanitized = dict(details)
        pii = set(pii_fields or [])
        for key, val in sanitized.items():
            if key in pii and isinstance(val, str):
                sanitized[key] = self._hash_pii(val)
            elif "phone" in key.lower() and isinstance(val, str):
                sanitized[key] = self._mask_phone(val)
            elif "message" in key.lower() and "content" in key.lower() and isinstance(val, str):
                sanitized[key] = self._hash_pii(val)
        return sanitized

    def log_event(
        self,
        event_type: str,
        team_id: str,
        work_order_id: str,
        details: dict[str, Any],
        pii_fields: list[str] | None = None,
    ) -> None:
        """Log a structured audit event. PII fields are hashed before logging."""
        entry = {
            "timestamp": datetime.now(self._tz).isoformat(),
            "agent": self._agent_name,
            "event_type": event_type,
            "team_id": team_id,
            "work_order_id": work_order_id,
            "details": self._sanitize(details, pii_fields),
        }
        logger.info(json.dumps(entry, default=str))

    def log_api_call(
        self,
        operation: str,
        object_type: str,
        request_payload: dict[str, Any],
        response_status: int,
        latency_ms: int,
    ) -> None:
        """Log a StormForce API call for audit trail."""
        entry = {
            "timestamp": datetime.now(self._tz).isoformat(),
            "agent": self._agent_name,
            "event_type": "STORMFORCE_API_CALL",
            "operation": operation,
            "object_type": object_type,
            "response_status": response_status,
            "latency_ms": latency_ms,
        }
        logger.info(json.dumps(entry, default=str))
