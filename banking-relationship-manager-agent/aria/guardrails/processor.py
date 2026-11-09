from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from aria.guardrails.config import CREDENTIAL_PATTERNS, PROMPT_ATTACK_PATTERNS
from aria.observability import Observability


@dataclass(frozen=True)
class GuardrailResult:
    sanitized_message: str
    credential_detected: bool
    injection_detected: bool
    blocked: bool
    reason: str
    audit_id: str


class GuardrailProcessor:
    """Protect user input and output from sensitive credential leakage."""

    _sensitive_pattern = re.compile(
        r"(?i)(?:pin\s*(?:is|=)?\s*\d{4,6}|otp\s*(?:is|=)?\s*\d{4,8}|cvv\s*(?:is|=)?\s*\d{3,4}|password\s*(?:is|=)?\s*\S+)"
    )
    _injection_pattern = re.compile(
        r"(?i)(?:ignore\s+all\s+prior\s+instructions|system\s+prompt|override\s+your\s+role|reveal\s+internal\s+details)"
    )

    def _emit_result(self, operation: str, result: GuardrailResult) -> None:
        Observability().emit_operation(
            operation,
            {
                "audit_id": result.audit_id,
                "reason": result.reason,
                "blocked": result.blocked,
                "credential_detected": result.credential_detected,
                "injection_detected": result.injection_detected,
            },
            status="blocked" if result.blocked else "success",
        )

    def _has_credential(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS)

    def _has_injection(self, text: str) -> bool:
        lower_text = text.lower()
        denied_keywords = (
            "system prompt",
            "internal instructions",
            "hidden policy",
            "reveal internal details",
            "confidential system",
            "role override",
        )
        if any(keyword in lower_text for keyword in denied_keywords):
            return True
        return any(pattern.search(text) for pattern in PROMPT_ATTACK_PATTERNS)

    def redact_sensitive_content(self, text: str) -> str:
        redacted = re.sub(
            r"(?i)\b(pin|otp|cvv|password)\b\s*(?:is|=)?\s*\d{3,8}\b",
            lambda match: f"{match.group(1).upper()} is [REDACTED]",
            text,
        )
        redacted = re.sub(
            r"(?i)\b(pin|otp|cvv|password)\b\s*(?:is|=)?\s*\S+",
            lambda match: f"{match.group(1).upper()} is [REDACTED]",
            redacted,
        )
        redacted = re.sub(r"\b\d{3,8}\b", "[REDACTED]", redacted)
        return redacted

    def process_input(self, text: str) -> GuardrailResult:
        sanitized = self.redact_sensitive_content(text)
        credential_detected = self._has_credential(text)
        injection_detected = self._has_injection(text)
        blocked = credential_detected or injection_detected

        if credential_detected and injection_detected:
            reason = "credential_and_prompt_injection_detected"
        elif credential_detected:
            reason = "credential_detected"
        elif injection_detected:
            reason = "prompt_injection_detected"
        else:
            reason = "safe"

        result = GuardrailResult(
            sanitized_message=sanitized,
            credential_detected=credential_detected,
            injection_detected=injection_detected,
            blocked=blocked,
            reason=reason,
            audit_id=uuid.uuid4().hex,
        )
        self._emit_result("guardrail.input", result)
        return result

    def process_output(self, text: str) -> GuardrailResult:
        sanitized = self.redact_sensitive_content(text)
        credential_detected = self._has_credential(text)
        injection_detected = self._has_injection(text)
        blocked = credential_detected or injection_detected

        if credential_detected and injection_detected:
            reason = "credential_and_prompt_injection_detected"
        elif credential_detected:
            reason = "credential_detected"
        elif injection_detected:
            reason = "prompt_injection_detected"
        else:
            reason = "sensitive_content_detected" if sanitized != text else "safe"

        result = GuardrailResult(
            sanitized_message=sanitized,
            credential_detected=credential_detected,
            injection_detected=injection_detected,
            blocked=blocked,
            reason=reason,
            audit_id=uuid.uuid4().hex,
        )
        self._emit_result("guardrail.output", result)
        return result

    def validate(self, text: str) -> bool:
        if self._injection_pattern.search(text):
            return False
        return not bool(self._sensitive_pattern.search(text))
