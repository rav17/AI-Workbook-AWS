# Quickstart: Receivables Exception Resolution MVP

## Prerequisites

- Python 3.11 and project dependencies.
- A reviewed single-customer, single-currency synthetic/de-identified fixture.
- An approved procedure, tolerance table, matching weights, confidence thresholds, and labelled test set from the receivables/control owner.
- Fake source adapters and fake case-task writer for local tests; no AWS credentials are required for unit/contract tests.

Do not connect live payment, customer, virtual-account, invoice, or case systems in this MVP.

## Local validation

From the repository root:

```powershell
python -m pytest tests/unit/test_receivables_rules.py tests/framework/test_receivables_subagent.py
```

The deterministic rule suite should verify mapping status/effective dates, invoice eligibility, currency, variance/tolerance, duplicate/prior allocation, candidate conflicts, and no-recommendation outcomes before any model behavior is tested.

## Investigation walkthrough

1. Seed a payment exception and its virtual-account/customer/invoice evidence using the approved fixture.
2. Ask Aria to investigate; verify the parent delegates only the bounded exception request to the specialist.
3. Inspect the plan, read-only evidence references, deterministic checks, policy version, candidate ranking, confidence, and draft operations note.
4. Submit analyst `revise`, `reject`, or `escalate` and verify no write occurs.
5. Submit an authorized `approve` and verify exactly one idempotent case task is created/updated.
6. Confirm no ledger, account, payment, virtual-account, customer, or invoice mutation tool exists or is called.
7. Replay the labelled evaluation set and report classification, top-candidate, confident-allocation precision, escalation, evidence, variance, and prohibited-write measures separately.

## Demo acceptance

Use the worked example only with owner-approved test tolerance values; the illustrative 500-unit variance in the source PDF is not a default policy. Missing policy data, source conflicts, duplicate suspicion, or low confidence must return an explicit no-recommendation/escalation outcome.
