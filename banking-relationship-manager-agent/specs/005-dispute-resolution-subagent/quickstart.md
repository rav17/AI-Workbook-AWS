# Quickstart: Dispute Resolution MVP

## Prerequisites

- Python 3.11 and project dependencies.
- One mock/de-identified customer/payment dataset and one currency.
- Owner-approved test policy, evidence fields, analyst-role mapping, and labelled test set.
- Fake source adapters and simulated action adapter; no AWS source credentials are required for unit tests.

Do not connect live payment, card, merchant, account, or ledger systems in this MVP.

## Local validation

From the repository root:

```powershell
python -m pytest tests/unit/test_receivables_rules.py tests/framework/test_receivables_subagent.py tests/unit/test_receivables_approval.py
```

Run deterministic rules tests before subagent tests. Verify policy absence, failed checks, duplicate suspicion, and conflicting evidence all produce no recommendation or human review.

## Controlled walkthrough

1. Load a labelled synthetic fraudulent-transaction case and ask Aria to investigate it.
2. Inspect the read-only evidence references, investigation steps, deterministic findings, test-only policy version, and simulated proposal.
3. Run a merchant non-delivery case with insufficient delivery evidence and confirm it routes to human review.
4. Exercise analyst revise, reject, escalate, and approve decisions with verified test identities.
5. Confirm only approval produces a simulated action event and no actual card, refund, payment, account, ledger, or master-data connector is available.
6. Replay the owner-approved evaluation set and record classification, top-candidate accuracy, confident precision, escalation, evidence coverage, variance checks, and prohibited-write counts.

## MVP acceptance evidence

The prototype remains mock/de-identified only. Do not report production readiness or live dispute resolution until source contracts, access permissions, approved policies, operational controls, and separate integration approvals exist.
