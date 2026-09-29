from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryEntry:
    key: str
    value: str
    tenant_id: str


@dataclass
class MemoryStore:
    entries: list[MemoryEntry] = field(default_factory=list)

    def retrieve(self, tenant_id: str, limit: int = 5) -> list[MemoryEntry]:
        matches = [entry for entry in self.entries if entry.tenant_id == tenant_id]
        return matches[:limit]

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)
