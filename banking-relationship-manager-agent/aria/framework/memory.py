from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class MemoryEntry:
    key: str
    value: str
    tenant_id: str
    expires_at: datetime | None = None


@dataclass
class MemoryStore:
    entries: list[MemoryEntry] = field(default_factory=list)

    def retrieve(self, tenant_id: str, limit: int = 5) -> list[MemoryEntry]:
        now = datetime.now(UTC)
        matches = [
            entry
            for entry in self.entries
            if entry.tenant_id == tenant_id and (entry.expires_at is None or entry.expires_at > now)
        ]
        return matches[:limit]

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)

    def delete(self, tenant_id: str, key: str | None = None) -> int:
        original_count = len(self.entries)
        self.entries = [
            entry
            for entry in self.entries
            if entry.tenant_id != tenant_id or (key is not None and entry.key != key)
        ]
        return original_count - len(self.entries)
