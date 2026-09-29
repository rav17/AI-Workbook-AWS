from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowResult:
    valid: bool
    state: dict[str, Any] = field(default_factory=dict)
    next_step: str | None = None
    errors: list[str] = field(default_factory=list)
