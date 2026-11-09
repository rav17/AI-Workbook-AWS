# Contract: Receivables Investigation and Analyst Approval

## Aria parent-to-specialist handoff

The existing Aria parent exposes one bounded specialist tool named `receivables_exception_investigator`. It receives:

```json
{
  "exception_id": "EXC-0001",
  "payment_id": "PAY-0001",
  "exception_type": "amount_reference_mismatch",
  "customer_scope": "CORP-001",
  "currency": "USD",
  "session_context": "The analyst is investigating the March inbound payment queue."
}
```

- Parent Aria supplies the verified principal/session context and retains final response ownership.
- Only the three in-scope exception types and configured single-customer/single-currency values are accepted.
- The specialist cannot invent source records, customer identity, invoice identifiers, policy values, or analyst approval.
- The child agent has no generic write tool and cannot invoke ledger/account/virtual-account operations.

## Investigation result

A successful investigation returns a structured proposal:

```json
{
  "outcome": "recommend | no_recommendation | escalate",
  "exception_id": "EXC-0001",
  "exception_reason": "amount_reference_mismatch",
  "customer_id": "CORP-001",
  "invoice_id": "INV-0001",
  "confidence_band": "configured-band",
  "variance": {
    "payment_amount": "499500.00",
    "expected_amount": "500000.00",
    "variance_amount": "500.00",
    "currency": "USD",
    "tolerance_rule_id": "POLICY-V3"
  },
  "evidence": [
    {"source_type": "payment", "source_record_id": "PAY-0001"},
    {"source_type": "virtual_account", "source_record_id": "VA-0001"},
    {"source_type": "invoice", "source_record_id": "INV-0001"},
    {"source_type": "procedure", "source_record_id": "POLICY-V3"}
  ],
  "draft_operations_note": "...",
  "requires_analyst_decision": true
}
```

A `no_recommendation` result MUST omit the proposed invoice allocation and explain the failed/missing evidence. Duplicate or unresolved prior-allocation checks MUST never return a confident recommendation.

## Analyst decision

```json
{
  "exception_id": "EXC-0001",
  "recommendation_id": "REC-0001",
  "recommendation_version": 1,
  "decision": "approve | revise | reject | escalate",
  "analyst_id": "ANALYST-001",
  "rationale": "...",
  "revision": {"invoice_id": "INV-0002"}
}
```

- `analyst_id` is verified by the analyst interface, not supplied by the model.
- `revise` reruns all deterministic eligibility, variance, tolerance, and duplicate checks and returns a new version for approval.
- `reject` and `escalate` are audited and do not invoke the case-task writer.
- `approve` invokes only the idempotent case-management task writer.

## Permitted write contract

The case writer accepts only a validated approved decision with the matching recommendation version and idempotency key. It can create/update a case task only. It has no method or permission for ledger posting, account credit, payment return/repair, virtual-account changes, or source master-data updates.

## Audit contract

Every source retrieval, deterministic check, model proposal, analyst revision/decision, and case-task result emits a correlated audit event with sequence, actor, source references, policy version, and safe summary. Raw prompt text, credentials, and hidden reasoning are excluded.
