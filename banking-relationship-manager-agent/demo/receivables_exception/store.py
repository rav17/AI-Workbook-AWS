from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from aria.agents.aria.receivables.models import (
    AnalystDecision,
    AuditEvent,
    CaseTask,
    ConfirmationBinding,
    DecisionKind,
    InvestigationProposal,
    MockCaseTaskPayload,
    Outcome,
    TrustedContext,
)
from aria.agents.aria.receivables.policy import canonical_json_bytes
from aria.agents.aria.receivables.trusted_context import require_context


class StoreError(RuntimeError):
    """Local SQLite transaction did not commit successfully."""


class _MeasuredConnection(sqlite3.Connection):
    """Count actual SQL execute attempts/successes, never payloads or inferred coverage.

    Success here means SQL returned; transactions may subsequently roll back.
    Initialization DDL via executescript is deliberately outside these DML counters.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        surfaces = (
            f"{operation}:{table}"
            for table in ("proposals", "states", "decisions", "bindings", "case_tasks", "audit")
            for operation in ("insert", "update", "delete")
        )
        self.write_calls: Counter[str] = Counter(dict.fromkeys(surfaces, 0))
        self.write_attempts: Counter[str] = self.write_calls.copy()

    def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
        match = re.match(r"\s*(INSERT(?: OR \w+)? INTO|UPDATE|DELETE FROM)\s+(\w+)", sql, re.I)
        surface = f"{match[1].split()[0].lower()}:{match[2].lower()}" if match else None
        if surface is not None:
            self.write_attempts[surface] += 1
        result = super().execute(sql, parameters)
        if surface is not None:
            self.write_calls[surface] += 1
        return result


class LocalSQLiteStore:
    """Isolated synthetic workflow state; only case_tasks is a business-write table."""

    def __init__(self, path: str | Path, *, audit_failure: bool = False) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.audit_failure = audit_failure
        self.clock: Any | None = None
        self._lock = threading.RLock()
        self.audit_failures: Counter[str] = Counter()
        self._db = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False, factory=_MeasuredConnection
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS proposals(
                tenant TEXT, session TEXT, proposal_id TEXT, exception_id TEXT,
                version INTEGER, payload TEXT, PRIMARY KEY(tenant,session,proposal_id),
                UNIQUE(tenant,session,exception_id,version));
            CREATE TABLE IF NOT EXISTS states(
                tenant TEXT, session TEXT, exception_id TEXT, proposal_id TEXT,
                proposal_version INTEGER,
                decision_revision INTEGER DEFAULT 0, state TEXT,
                PRIMARY KEY(tenant,session,exception_id));
            CREATE TABLE IF NOT EXISTS decisions(
                decision_id TEXT PRIMARY KEY, tenant TEXT, session TEXT, exception_id TEXT,
                proposal_id TEXT, proposal_version INTEGER, decision TEXT, revision INTEGER,
                rationale TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS bindings(
                confirmation_id TEXT PRIMARY KEY, tenant TEXT, session TEXT, exception_id TEXT,
                proposal_id TEXT, proposal_version INTEGER, decision_revision INTEGER,
                payload_hash TEXT,
                payload_json TEXT, context_binding TEXT, created_at TEXT, expires_at TEXT,
                UNIQUE(tenant,session,exception_id,proposal_id,proposal_version,
                       decision_revision));
            CREATE TABLE IF NOT EXISTS case_tasks(
                case_task_id TEXT PRIMARY KEY, confirmation_id TEXT UNIQUE, payload_hash TEXT,
                payload_json TEXT, tenant TEXT, session TEXT, created_at TEXT,
                FOREIGN KEY(confirmation_id) REFERENCES bindings(confirmation_id));
            CREATE TABLE IF NOT EXISTS audit(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT, session TEXT, event_json TEXT);
            CREATE TRIGGER IF NOT EXISTS no_proposal_update BEFORE UPDATE ON proposals
              BEGIN SELECT RAISE(ABORT,'proposals are immutable versions'); END;
            CREATE TRIGGER IF NOT EXISTS no_proposal_delete BEFORE DELETE ON proposals
              BEGIN SELECT RAISE(ABORT,'proposals are immutable versions'); END;
            CREATE TRIGGER IF NOT EXISTS no_binding_update BEFORE UPDATE ON bindings
              BEGIN SELECT RAISE(ABORT,'confirmation bindings are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS no_binding_delete BEFORE DELETE ON bindings
              BEGIN SELECT RAISE(ABORT,'confirmation bindings are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS no_decision_update BEFORE UPDATE ON decisions
              BEGIN SELECT RAISE(ABORT,'decisions are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_decision_delete BEFORE DELETE ON decisions
              BEGIN SELECT RAISE(ABORT,'decisions are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_audit_update BEFORE UPDATE ON audit
              BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_audit_delete BEFORE DELETE ON audit
              BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_task_update BEFORE UPDATE ON case_tasks
              BEGIN SELECT RAISE(ABORT,'case tasks are create-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_task_delete BEFORE DELETE ON case_tasks
              BEGIN SELECT RAISE(ABORT,'case tasks are create-only'); END;
        """)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @staticmethod
    def _context_binding(context: TrustedContext) -> str:
        safe = {
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "analyst_role": context.analyst_role,
        }
        return hashlib.sha256(canonical_json_bytes(safe)).hexdigest()

    @staticmethod
    def _event(
        context: TrustedContext,
        kind: str,
        summary: str,
        proposal: InvestigationProposal | None = None,
        confirmation_id: str | None = None,
        task_id: str | None = None,
        refs: tuple[str, ...] = (),
    ) -> AuditEvent:
        return AuditEvent(
            event_id=str(uuid4()),
            correlation_id=context.correlation_id,
            sequence=0,
            event_type=kind,
            actor=context.user_id,
            source_refs=refs,
            policy_version=proposal.policy_version if proposal else None,
            reason_codes=(proposal.primary_reason,) if proposal else (),
            proposal_version=proposal.version if proposal else None,
            proposal_id=proposal.proposal_id if proposal else None,
            confirmation_id=confirmation_id,
            case_task_id=task_id,
            safe_summary=summary[:500],
            created_at=datetime.now(UTC),
        )

    def _audit(self, context: TrustedContext, event: AuditEvent) -> None:
        if self.audit_failure:
            key = event.event_type
            if key == "retrieval":
                key += ":" + event.safe_summary.split()[1]
            self.audit_failures[key] += 1
            raise StoreError("audit sink failed; operation rolled back")
        sequence = int(
            self._db.execute("SELECT COALESCE(MAX(seq),0)+1 AS n FROM audit").fetchone()["n"]
        )
        persisted = event.model_copy(update={"sequence": sequence})
        self._db.execute(
            "INSERT INTO audit(tenant,session,event_json) VALUES (?,?,?)",
            (context.tenant_id, context.session_id, persisted.model_dump_json()),
        )

    def measurements(self) -> dict[str, Any]:
        with self._lock:
            connection = self._db
            assert isinstance(connection, _MeasuredConnection)
            return {
                "write_attempts": dict(connection.write_attempts),
                "write_calls": dict(connection.write_calls),
                "committed_rows": {
                    table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "proposals",
                        "states",
                        "decisions",
                        "bindings",
                        "case_tasks",
                        "audit",
                    )
                },
                "audit_failures": dict(self.audit_failures),
            }

    def record_proposal_output(
        self, context: TrustedContext, proposal: InvestigationProposal
    ) -> None:
        """Audit a successful transient recheck without persisting it as analyst state."""
        self.append_event(
            context,
            self._event(
                context,
                "proposal",
                f"Returned transient proposal {proposal.version}: {proposal.outcome.value}",
                proposal,
                refs=tuple(item.source_record_id for item in proposal.evidence),
            ),
        )

    def _insert_proposal(self, context: TrustedContext, proposal: InvestigationProposal) -> None:
        self._db.execute(
            "INSERT INTO proposals VALUES (?,?,?,?,?,?)",
            (
                context.tenant_id,
                context.session_id,
                proposal.proposal_id,
                proposal.exception_id,
                proposal.version,
                proposal.model_dump_json(),
            ),
        )
        self._db.execute(
            "INSERT INTO states VALUES (?,?,?,?,?,0,'awaiting_analyst') "
            "ON CONFLICT(tenant,session,exception_id) DO UPDATE SET "
            "proposal_id=excluded.proposal_id, "
            "proposal_version=excluded.proposal_version,state='awaiting_analyst'",
            (
                context.tenant_id,
                context.session_id,
                proposal.exception_id,
                proposal.proposal_id,
                proposal.version,
            ),
        )
        self._audit(
            context,
            self._event(
                context,
                "proposal",
                f"Proposal {proposal.version} stored: {proposal.outcome.value}",
                proposal,
                refs=tuple(item.source_record_id for item in proposal.evidence),
            ),
        )

    def save_proposal(self, context: TrustedContext, proposal: InvestigationProposal) -> None:
        require_context(context)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._insert_proposal(context, proposal)
                self._db.execute("COMMIT")
            except Exception as exc:
                self._db.execute("ROLLBACK")
                if isinstance(exc, StoreError):
                    raise
                raise StoreError("proposal transaction failed") from exc

    def get_proposal(
        self, context: TrustedContext, proposal_id: str
    ) -> InvestigationProposal | None:
        require_context(context)
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM proposals WHERE tenant=? AND session=? AND proposal_id=?",
                (context.tenant_id, context.session_id, proposal_id),
            ).fetchone()
        return InvestigationProposal.model_validate_json(row["payload"]) if row else None

    def get_current_proposal(
        self, context: TrustedContext, exception_id: str
    ) -> InvestigationProposal | None:
        require_context(context)
        with self._lock:
            row = self._db.execute(
                "SELECT proposal_id FROM states WHERE tenant=? AND session=? AND exception_id=?",
                (context.tenant_id, context.session_id, exception_id),
            ).fetchone()
        return self.get_proposal(context, row["proposal_id"]) if row else None

    def _new_decision(
        self,
        context: TrustedContext,
        proposal: InvestigationProposal,
        kind: DecisionKind,
        rationale: str,
        revision: int,
        now: datetime,
    ) -> AnalystDecision:
        return AnalystDecision(
            decision_id=str(uuid4()),
            proposal_id=proposal.proposal_id,
            proposal_version=proposal.version,
            decision=kind,
            analyst_id=context.user_id,
            decision_revision=revision,
            rationale=rationale[:500],
            created_at=now,
        )

    def record_decision(
        self,
        context: TrustedContext,
        proposal_id: str,
        kind: DecisionKind,
        rationale: str = "",
        *,
        revised: InvestigationProposal | None = None,
    ) -> AnalystDecision:
        require_context(context)
        if kind == DecisionKind.APPROVE:
            raise StoreError("approval requires a bound payload")
        if (kind == DecisionKind.REVISE) != (revised is not None):
            raise StoreError("revision requires a prepared linked proposal")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                proposal = self.get_proposal(context, proposal_id)
                if proposal is None:
                    raise StoreError("proposal not found")
                state = self._db.execute(
                    "SELECT * FROM states WHERE tenant=? AND session=? AND exception_id=?",
                    (context.tenant_id, context.session_id, proposal.exception_id),
                ).fetchone()
                if (
                    state is None
                    or state["proposal_id"] != proposal_id
                    or state["proposal_version"] != proposal.version
                ):
                    raise StoreError("proposal is stale")
                if revised is not None and (
                    revised.exception_id != proposal.exception_id
                    or revised.payment_id != proposal.payment_id
                    or revised.version != proposal.version + 1
                    or revised.proposal_id
                    != f"{proposal.proposal_id.rsplit('-', 1)[0]}-{revised.version}"
                ):
                    raise StoreError("invalid revision link")
                revision = int(state["decision_revision"]) + 1
                now = datetime.now(UTC)
                decision = self._new_decision(context, proposal, kind, rationale, revision, now)
                self._db.execute(
                    "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        decision.decision_id,
                        context.tenant_id,
                        context.session_id,
                        proposal.exception_id,
                        proposal_id,
                        proposal.version,
                        kind.value,
                        revision,
                        rationale[:500],
                        now.isoformat(),
                    ),
                )
                state_name = {
                    DecisionKind.REVISE: "revised",
                    DecisionKind.REJECT: "rejected",
                    DecisionKind.ESCALATE: "escalated",
                }[kind]
                self._db.execute(
                    "UPDATE states SET decision_revision=?,state=? "
                    "WHERE tenant=? AND session=? AND exception_id=?",
                    (
                        revision,
                        state_name,
                        context.tenant_id,
                        context.session_id,
                        proposal.exception_id,
                    ),
                )
                self._audit(
                    context,
                    self._event(
                        context,
                        "decision",
                        f"Analyst decision: {kind.value}"
                        + (f"; revised to {revised.proposal_id}" if revised else ""),
                        proposal,
                        refs=(proposal.proposal_id, revised.proposal_id) if revised else (),
                    ),
                )
                if revised is not None:
                    self._insert_proposal(context, revised)
                self._db.execute("COMMIT")
                return decision
            except Exception as exc:
                self._db.execute("ROLLBACK")
                if isinstance(exc, StoreError):
                    raise
                raise StoreError("decision transaction failed") from exc

    def next_decision_revision(self, context: TrustedContext, exception_id: str) -> int:
        require_context(context)
        with self._lock:
            row = self._db.execute(
                "SELECT decision_revision FROM states "
                "WHERE tenant=? AND session=? AND exception_id=?",
                (context.tenant_id, context.session_id, exception_id),
            ).fetchone()
        if row is None:
            raise StoreError("proposal state is unavailable")
        return int(row["decision_revision"]) + 1

    def approve(
        self,
        context: TrustedContext,
        proposal_id: str,
        payload: MockCaseTaskPayload,
        confirmation_id: str,
        payload_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> ConfirmationBinding:
        require_context(context)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                proposal = self.get_proposal(context, proposal_id)
                if (
                    proposal is None
                    or proposal.outcome != Outcome.RECOMMEND
                    or payload.proposal_version != proposal.version
                    or now.tzinfo is None
                    or expires_at.tzinfo is None
                    or now > proposal.expires_at
                    or expires_at <= now
                ):
                    raise StoreError("approval unavailable for this proposal")
                if (
                    proposal.proposed_invoice_id is None
                    or proposal.payment_amount is None
                    or proposal.expected_amount is None
                    or proposal.variance is None
                    or proposal.policy_id is None
                    or proposal.policy_version is None
                ):
                    raise StoreError("recommendation is missing immutable task payload fields")
                expected_payload = MockCaseTaskPayload(
                    exception_id=proposal.exception_id,
                    proposal_id=proposal.proposal_id,
                    proposal_version=proposal.version,
                    payment_id=proposal.payment_id,
                    invoice_id=proposal.proposed_invoice_id,
                    customer_id="CORP-SYN-001",
                    currency=proposal.currency,
                    payment_amount=f"{proposal.payment_amount:.2f}",
                    expected_amount=f"{proposal.expected_amount:.2f}",
                    variance=f"{proposal.variance:+.2f}",
                    policy_id=proposal.policy_id,
                    policy_version=proposal.policy_version,
                    evidence_ids=tuple(
                        f"{item.source_type.value}:{item.source_record_id}"
                        for item in proposal.evidence
                    ),
                    decision_revision=payload.decision_revision,
                    summary=f"Synthetic receivables review for {proposal.exception_id}",
                )
                computed_hash = hashlib.sha256(
                    canonical_json_bytes(payload.model_dump(mode="json"))
                ).hexdigest()
                if payload != expected_payload or payload_hash != computed_hash:
                    raise StoreError("approval payload does not match the proposal binding")
                state = self._db.execute(
                    "SELECT * FROM states WHERE tenant=? AND session=? AND exception_id=?",
                    (context.tenant_id, context.session_id, proposal.exception_id),
                ).fetchone()
                if (
                    state is None
                    or state["proposal_id"] != proposal_id
                    or state["proposal_version"] != proposal.version
                    or state["state"] != "awaiting_analyst"
                ):
                    raise StoreError("proposal is stale or no longer awaiting analyst approval")
                revision = int(state["decision_revision"]) + 1
                if payload.decision_revision != revision:
                    raise StoreError("payload decision revision is stale")
                binding = ConfirmationBinding(
                    confirmation_id=confirmation_id,
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    exception_id=proposal.exception_id,
                    proposal_id=proposal_id,
                    proposal_version=proposal.version,
                    decision_revision=revision,
                    payload_hash=payload_hash,
                    context_binding=self._context_binding(context),
                )
                self._db.execute(
                    "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        context.tenant_id,
                        context.session_id,
                        proposal.exception_id,
                        proposal_id,
                        proposal.version,
                        "approve",
                        revision,
                        "",
                        now.isoformat(),
                    ),
                )
                self._db.execute(
                    "INSERT INTO bindings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        confirmation_id,
                        context.tenant_id,
                        context.session_id,
                        proposal.exception_id,
                        proposal_id,
                        proposal.version,
                        revision,
                        payload_hash,
                        payload.model_dump_json(),
                        binding.context_binding,
                        now.isoformat(),
                        expires_at.isoformat(),
                    ),
                )
                self._db.execute(
                    "UPDATE states SET decision_revision=?,state='approved_awaiting_confirmation' "
                    "WHERE tenant=? AND session=? AND exception_id=?",
                    (revision, context.tenant_id, context.session_id, proposal.exception_id),
                )
                self._audit(
                    context,
                    self._event(
                        context,
                        "decision",
                        "Analyst approved current proposal",
                        proposal,
                        confirmation_id,
                    ),
                )
                self._audit(
                    context,
                    self._event(
                        context,
                        "confirmation_binding",
                        "Opaque confirmation bound to immutable payload",
                        proposal,
                        confirmation_id,
                        refs=(payload_hash,),
                    ),
                )
                self._db.execute("COMMIT")
                return binding
            except Exception as exc:
                self._db.execute("ROLLBACK")
                if isinstance(exc, StoreError):
                    raise
                raise StoreError("approval transaction failed") from exc

    def get_binding(self, context: TrustedContext, confirmation_id: str) -> dict[str, Any] | None:
        require_context(context)
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM bindings WHERE confirmation_id=? AND tenant=? AND session=?",
                (confirmation_id, context.tenant_id, context.session_id),
            ).fetchone()
        if row is None or row["context_binding"] != self._context_binding(context):
            return None
        return dict(row)

    def _task_from_row(self, row: sqlite3.Row) -> CaseTask:
        return CaseTask(
            case_task_id=row["case_task_id"],
            confirmation_id=row["confirmation_id"],
            payload_hash=row["payload_hash"],
            payload=MockCaseTaskPayload.model_validate_json(row["payload_json"]),
            tenant_id=row["tenant"],
            session_id=row["session"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def append_event(self, context: TrustedContext, event: AuditEvent) -> None:
        require_context(context)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._audit(context, event)
                self._db.execute("COMMIT")
            except Exception as exc:
                self._db.execute("ROLLBACK")
                if isinstance(exc, StoreError):
                    raise
                raise StoreError("audit event was not committed") from exc

    def record_replay(self, context: TrustedContext, task: CaseTask) -> None:
        self.append_event(
            context,
            self._event(
                context,
                "replay",
                "Exact committed task replay",
                confirmation_id=task.confirmation_id,
                task_id=task.case_task_id,
                refs=(task.payload_hash,),
            ),
        )

    def replay(self, context: TrustedContext, confirmation_id: str) -> CaseTask | None:
        require_context(context)
        with self._lock:
            row = self._db.execute(
                "SELECT t.*,b.context_binding FROM case_tasks t "
                "JOIN bindings b USING(confirmation_id) "
                "WHERE t.confirmation_id=? AND b.tenant=? AND b.session=?",
                (confirmation_id, context.tenant_id, context.session_id),
            ).fetchone()
        if row is None or row["context_binding"] != self._context_binding(context):
            return None
        return self._task_from_row(row)

    def confirm(
        self,
        context: TrustedContext,
        confirmation_id: str,
        payload: MockCaseTaskPayload,
        payload_hash: str,
        now: datetime,
    ) -> tuple[str, CaseTask | None]:
        require_context(context)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                commit_time = self.clock.now() if self.clock is not None else now
                row = self._db.execute(
                    "SELECT * FROM bindings WHERE confirmation_id=? AND tenant=? AND session=?",
                    (confirmation_id, context.tenant_id, context.session_id),
                ).fetchone()
                if row is None:
                    raise StoreError("confirmation is unauthorized or unknown")
                binding = dict(row)
                stored_payload = MockCaseTaskPayload.model_validate_json(binding["payload_json"])
                computed_hash = hashlib.sha256(
                    canonical_json_bytes(payload.model_dump(mode="json"))
                ).hexdigest()
                stored_hash = hashlib.sha256(
                    canonical_json_bytes(stored_payload.model_dump(mode="json"))
                ).hexdigest()
                if (
                    binding["payload_hash"] != stored_hash
                    or binding["payload_hash"] != payload_hash
                    or payload_hash != computed_hash
                    or stored_payload != payload
                    or binding["context_binding"] != self._context_binding(context)
                ):
                    self._audit(
                        context,
                        self._event(
                            context,
                            "rejection",
                            "Changed confirmation binding rejected",
                            confirmation_id=confirmation_id,
                        ),
                    )
                    self._db.execute("COMMIT")
                    return "conflict", None
                existing = self._db.execute(
                    "SELECT * FROM case_tasks WHERE confirmation_id=?", (confirmation_id,)
                ).fetchone()
                if existing:
                    task = self._task_from_row(existing)
                    self._audit(
                        context,
                        self._event(
                            context,
                            "replay",
                            "Exact committed task replay",
                            confirmation_id=confirmation_id,
                            task_id=task.case_task_id,
                            refs=(payload_hash,),
                        ),
                    )
                    self._db.execute("COMMIT")
                    return "replayed", task
                state = self._db.execute(
                    "SELECT * FROM states WHERE tenant=? AND session=? AND exception_id=?",
                    (context.tenant_id, context.session_id, binding["exception_id"]),
                ).fetchone()
                proposal_row = self._db.execute(
                    "SELECT payload FROM proposals WHERE tenant=? AND session=? AND proposal_id=?",
                    (context.tenant_id, context.session_id, binding["proposal_id"]),
                ).fetchone()
                proposal = (
                    InvestigationProposal.model_validate_json(proposal_row["payload"])
                    if proposal_row is not None
                    else None
                )
                binding_expires_at = datetime.fromisoformat(binding["expires_at"])
                stale = (
                    proposal is None
                    or proposal.expires_at < commit_time
                    or state is None
                    or state["proposal_id"] != binding["proposal_id"]
                    or state["proposal_version"] != binding["proposal_version"]
                    or state["decision_revision"] != binding["decision_revision"]
                    or state["state"] != "approved_awaiting_confirmation"
                    or binding_expires_at < commit_time
                )
                if stale:
                    self._audit(
                        context,
                        self._event(
                            context,
                            "rejection",
                            "Stale confirmation rejected",
                            confirmation_id=confirmation_id,
                        ),
                    )
                    self._db.execute("COMMIT")
                    return "stale_confirmation", None
                if proposal is None:
                    raise StoreError("proposal is unavailable at confirmation commit")
                task_id = "TASK-SYN-" + uuid4().hex[:16].upper()
                self._db.execute(
                    "INSERT INTO case_tasks VALUES (?,?,?,?,?,?,?)",
                    (
                        task_id,
                        confirmation_id,
                        payload_hash,
                        payload.model_dump_json(),
                        context.tenant_id,
                        context.session_id,
                        commit_time.isoformat(),
                    ),
                )
                self._db.execute(
                    "UPDATE states SET state='task_created' "
                    "WHERE tenant=? AND session=? AND exception_id=?",
                    (context.tenant_id, context.session_id, binding["exception_id"]),
                )
                task = CaseTask(
                    case_task_id=task_id,
                    confirmation_id=confirmation_id,
                    payload_hash=payload_hash,
                    payload=payload,
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    created_at=commit_time,
                )
                self._audit(
                    context,
                    self._event(
                        context,
                        "confirmation",
                        "Explicit confirmation committed",
                        confirmation_id=confirmation_id,
                        task_id=task_id,
                        refs=(payload_hash,),
                    ),
                )
                self._audit(
                    context,
                    self._event(
                        context,
                        "task_result",
                        "Create-only mock task committed",
                        confirmation_id=confirmation_id,
                        task_id=task_id,
                        refs=(payload_hash,),
                    ),
                )
                final_commit_time = self.clock.now() if self.clock is not None else commit_time
                if (
                    proposal.expires_at < final_commit_time
                    or binding_expires_at < final_commit_time
                ):
                    self._db.execute("ROLLBACK")
                    self.append_event(
                        context,
                        self._event(
                            context,
                            "rejection",
                            "Confirmation expired before transaction commit",
                            confirmation_id=confirmation_id,
                        ).model_copy(update={"created_at": final_commit_time}),
                    )
                    return "stale_confirmation", None
                self._db.execute("COMMIT")
                return "created", task
            except Exception as exc:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                if isinstance(exc, StoreError):
                    raise
                raise StoreError("task transaction failed; result is unconfirmed") from exc

    def audit_events(self, context: TrustedContext) -> list[AuditEvent]:
        require_context(context)
        with self._lock:
            rows = self._db.execute(
                "SELECT event_json FROM audit WHERE tenant=? AND session=? ORDER BY seq",
                (context.tenant_id, context.session_id),
            ).fetchall()
        return [AuditEvent.model_validate_json(row["event_json"]) for row in rows]

    def task_count(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COUNT(*) AS n FROM case_tasks").fetchone()
        return int(row["n"])
