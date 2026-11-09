# Contract: Dispute Investigation and Human Review

## Aria parent-to-specialist handoff

The existing Aria parent exposes one bounded specialist tool named `dispute_resolution_specialist`.

```json
{
  "case_id": "CASE-001",
  "dispute_type": "fraudulent_transaction",
  "transaction_id": "TXN-001",
  "claim": "I do not recognize this transaction.",
  "session_context": "The customer reports no travel during the transaction period."
}
```

- Aria supplies verified customer/tenant/session context outside the request body.
- Only configured dispute types and transaction scope are accepted.
- The specialist returns an investigation plan, evidence references, findings, and a recommendation; it cannot self-authorize an action.

## Specialist result

```json
{
  "outcome": "propose_resolution | human_review | no_recommendation",
  "case_id": "CASE-001",
  "dispute_type": "fraudulent_transaction",
  "explanation": "...",
  "findings": [
    {"summary": "...", "evidence_ids": ["TXN-001", "ACCOUNT-002"], "check": "passed"}
  ],
  "policy_version": "TEST-POLICY-1",
  "confidence": {"band": "review | eligible_for_simulation", "basis": ["..."]},
  "simulated_actions": ["simulate_card_block"],
  "requires_human_decision": true
}
```

`simulated_actions` are demo proposals only. Missing policy, insufficient/conflicting evidence, and failed deterministic checks produce `human_review` or `no_recommendation` and an empty action list.

## Human decision

```json
{
  "case_id": "CASE-001",
  "recommendation_id": "REC-001",
  "recommendation_version": 1,
  "decision": "approve | revise | reject | escalate",
  "analyst_id": "ANALYST-001",
  "rationale": "...",
  "revision": {}
}
```

- Analyst identity must be verified by the review interface and cannot be model supplied.
- `revise` re-runs relevant deterministic checks and returns a new recommendation version.
- `reject` and `escalate` emit audit events and do not run simulated actions.
- `approve` records approval of the simulation only. No production card/refund/ledger connector exists.

## Safe activity and audit events

Allowed events include `case.received`, `investigation.step`, `evidence.retrieved`, `rule.checked`, `recommendation.ready`, `human.decision`, `action.simulated`, and `case.escalated`.

Each event carries a correlation ID, case ID, sequence, safe summary, source references, and policy/recommendation version where applicable. Events MUST NOT expose private chain-of-thought, credentials, or unbounded raw source payloads.
