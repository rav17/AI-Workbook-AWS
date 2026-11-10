from __future__ import annotations

import re

CREDENTIAL_PATTERNS = [
    re.compile(r"(?i)\b(pin|otp|cvv|password|passcode)\b\s*(?:is|=|:)?\s*\S+"),
    re.compile(r"(?i)\b(pin|otp|cvv|password|passcode)\b\s*(?:is|=|:)?\s*\d{3,8}\b"),
]

PROMPT_ATTACK_PATTERNS = [
    re.compile(r"(?i)ignore\s+all\s+prior\s+instructions"),
    re.compile(r"(?i)reveal\s+(?:the\s+)?system\s+prompt"),
    re.compile(r"(?i)override\s+your\s+role"),
    re.compile(r"(?i)do\s+not\s+mention\s+internal\s+details"),
]

__all__ = ["CREDENTIAL_PATTERNS", "PROMPT_ATTACK_PATTERNS"]
