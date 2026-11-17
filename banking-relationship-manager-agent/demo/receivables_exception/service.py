from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from aria.agents.aria.receivables.engine import ReceivablesInvestigationEngine
from aria.agents.aria.receivables.models import (
    DecisionKind,
    InvestigationProposal,
    MockCaseTaskPayload,
    Outcome,
    TrustedContext,
)
from aria.agents.aria.receivables.policy import canonical_json_bytes
from aria.agents.aria.receivables.trusted_context import require_context
from demo.receivables_exception.store import LocalSQLiteStore, StoreError


class ReceivablesWorkflowService:
    def __init__(
        self,
        engine: ReceivablesInvestigationEngine,
        store: LocalSQLiteStore,
        clock: Any | None = None,
    ) -> None:
        self.engine = engine
        self.store = store
        self.clock = clock or engine.clock
        self.store.clock = self.clock
        if getattr(self.engine, "audit_sink", None) is None:
            self.engine.audit_sink = self.store.append_event
        # Persisted outputs are audited atomically by save_proposal; transient outputs
        # are explicitly audited by this service after a successful engine return.
        self.engine.audit_proposals = False

    def investigate(
        self,
        context: TrustedContext,
        payment_id: str,
        exception_type: str = "amount_reference_mismatch",
    ) -> InvestigationProposal:
        require_context(context)
        proposal = self.engine.investigate(context, payment_id, exception_type)
        self.store.save_proposal(context, proposal)
        return proposal

    def decide(
        self,
        context: TrustedContext,
        proposal_id: str,
        decision: DecisionKind | str,
        rationale: str = "",
    ) -> dict[str, Any]:
        require_context(context)
        kind = DecisionKind(decision)
        proposal = self.store.get_proposal(context, proposal_id)
        if proposal is None:
            raise StoreError("proposal is unavailable in this context")
        now = self.clock.now()
        if kind == DecisionKind.APPROVE:
            if proposal.outcome != Outcome.RECOMMEND or now > proposal.expires_at:
                raise StoreError(
                    "approval unavailable for a non-recommendation or expired proposal"
                )
            revision = self.store.next_decision_revision(context, proposal.exception_id)
            payload = self._payload(proposal, revision)
            payload_hash = hashlib.sha256(
                canonical_json_bytes(payload.model_dump(mode="json"))
            ).hexdigest()
            confirmation_id = "CNF-SYN-" + secrets.token_urlsafe(24)
            binding = self.store.approve(
                context,
                proposal_id,
                payload,
                confirmation_id,
                payload_hash,
                now,
                now + timedelta(minutes=self.engine.catalogue.policy.confirmation_window_minutes),
            )
            return {
                "decision": "approve",
                "confirmation_id": binding.confirmation_id,
                "proposal_version": binding.proposal_version,
                "payload": payload,
                "payload_hash": payload_hash,
            }
        if kind == DecisionKind.REVISE:
            revised = self.engine.investigate(
                context,
                proposal.payment_id,
                proposal.classification
                if proposal.classification in self.engine.catalogue.policy.exception_types
                else "amount_reference_mismatch",
            )
            base = proposal.proposal_id.rsplit("-", 1)[0]
            revised_id = f"{base}-{proposal.version + 1}"
            revised = revised.model_copy(
                update={"proposal_id": revised_id, "version": proposal.version + 1}
            )
            # Prepare first: investigation failures leave analyst state unchanged.
            # The store commits decision, immutable link, proposal and audits together.
            decision_record = self.store.record_decision(
                context, proposal_id, kind, rationale, revised=revised
            )
            return {"decision": decision_record, "proposal": revised}
        decision_record = self.store.record_decision(context, proposal_id, kind, rationale)
        return {"decision": decision_record, "task_created": False}

    def confirm(
        self,
        context: TrustedContext,
        confirmation_id: str,
        displayed_payload_hash: str | None = None,
        displayed_proposal_version: int | None = None,
    ) -> dict[str, Any]:
        require_context(context)
        binding = self.store.get_binding(context, confirmation_id)
        if binding is None:
            return {"status": "unauthorized", "task": None}
        if (
            displayed_payload_hash is None
            or displayed_proposal_version is None
            or displayed_payload_hash != binding["payload_hash"]
            or displayed_proposal_version != int(binding["proposal_version"])
        ):
            return {"status": "binding_mismatch", "task": None}
        # Exact committed replay is resolved before stale-state or evidence checks.
        replay = self.store.replay(context, confirmation_id)
        if replay is not None:
            try:
                self.store.record_replay(context, replay)
            except StoreError:
                return {
                    "status": "unconfirmed",
                    "task": None,
                    "safe_next_step": (
                        "Check local task status before retrying the same confirmation."
                    ),
                }
            return {"status": "replayed", "task": replay}
        payload = MockCaseTaskPayload.model_validate_json(binding["payload_json"])
        proposal = self.store.get_proposal(context, payload.proposal_id)
        now = self.clock.now()
        if (
            proposal is None
            or now > proposal.expires_at
            or now > datetime.fromisoformat(binding["expires_at"])
        ):
            return {"status": "stale_confirmation", "task": None}
        try:
            current = self.engine.investigate(
                context,
                proposal.payment_id,
                proposal.classification
                if proposal.classification in self.engine.catalogue.policy.exception_types
                else "amount_reference_mismatch",
            )
            self.store.record_proposal_output(context, current)
        except StoreError:
            return {
                "status": "unconfirmed",
                "task": None,
                "safe_next_step": (
                    "Check local task status and retry the same confirmation "
                    "after audit is available."
                ),
            }
        if (
            current.outcome != Outcome.RECOMMEND
            or current.snapshot is None
            or proposal.snapshot is None
            or current.snapshot.aggregate_digest != proposal.snapshot.aggregate_digest
        ):
            return {"status": "stale_confirmation", "task": None}
        try:
            status, task = self.store.confirm(
                context, confirmation_id, payload, binding["payload_hash"], now
            )
        except StoreError:
            return {
                "status": "unconfirmed",
                "task": None,
                "safe_next_step": (
                    "Check local task status, then retry with this same confirmation ID."
                ),
            }
        return {"status": status, "task": task}

    @staticmethod
    def _payload(proposal: InvestigationProposal, revision: int) -> MockCaseTaskPayload:
        if (
            proposal.outcome != Outcome.RECOMMEND
            or proposal.proposed_invoice_id is None
            or proposal.payment_amount is None
            or proposal.expected_amount is None
            or proposal.variance is None
            or proposal.policy_id is None
            or proposal.policy_version is None
        ):
            raise StoreError("proposal cannot produce a mock task payload")
        return MockCaseTaskPayload(
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
                f"{item.source_type.value}:{item.source_record_id}" for item in proposal.evidence
            ),
            decision_revision=revision,
            summary=f"Synthetic receivables review for {proposal.exception_id}",
        )
