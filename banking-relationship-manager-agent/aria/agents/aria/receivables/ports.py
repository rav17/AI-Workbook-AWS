from __future__ import annotations

from datetime import datetime
from typing import Protocol

from aria.agents.aria.receivables.models import (
    AuditEvent,
    EvidenceType,
    InvestigationProposal,
    SourceResult,
    TrustedContext,
)


class ReadOnlySource(Protocol):
    def read(
        self, context: TrustedContext, source_type: EvidenceType, key: str
    ) -> SourceResult: ...


class AuditSink(Protocol):
    def append(self, event: AuditEvent) -> None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...


class ProposalStore(Protocol):
    def save_proposal(self, context: TrustedContext, proposal: InvestigationProposal) -> None: ...

    def get_proposal(
        self, context: TrustedContext, proposal_id: str
    ) -> InvestigationProposal | None: ...
