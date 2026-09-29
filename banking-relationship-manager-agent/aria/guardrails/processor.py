from __future__ import annotations

import re


class GuardrailProcessor:
    """Protect user input and output from sensitive credential leakage."""

    _sensitive_pattern = re.compile(
        r"(?i)(?:pin\s*(?:is|=)?\s*\d{4,6}|otp\s*(?:is|=)?\s*\d{4,8}|cvv\s*(?:is|=)?\s*\d{3,4}|password\s*(?:is|=)?\s*\S+)"
    )
    _injection_pattern = re.compile(
        r"(?i)(?:ignore\s+all\s+prior\s+instructions|system\s+prompt|override\s+your\s+role|reveal\s+internal\s+details)"
    )

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

    def validate(self, text: str) -> bool:
        if self._injection_pattern.search(text):
            return False
        return not bool(self._sensitive_pattern.search(text))
