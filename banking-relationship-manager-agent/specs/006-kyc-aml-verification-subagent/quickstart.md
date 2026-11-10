# Quickstart: KYC/AML Verification Subagent

## Prerequisites

- Python 3.11 and project dependencies.
- Fake document extraction, verification-source, and policy providers for local tests.
- Synthetic identity values only; do not use real identity documents or identifiers.

No live provider credentials or AWS account are needed for local contract tests. Real integrations remain blocked until compliance owners approve provider contracts, source access, jurisdiction rules, thresholds, and retention.

## Local validation

From the repository root:

```powershell
python -m pytest tests/unit/test_kyc_aml_verification.py tests/framework/test_kyc_aml_subagent.py tests/unit/test_service_and_compliance.py
```

Verify extraction observations are typed/masked, multiple source observations yield deterministic match/conflict results, missing providers/policies fail closed, and raw document values do not appear in prompts, logs, audit, or Memory.

## Walkthrough

1. Submit a synthetic document reference through an authenticated Aria parent request.
2. Verify the child reports extracted fields with confidence and provenance, not raw content.
3. Verify source fakes produce field-level matches, mismatches, unavailable sources, and stale evidence as expected.
4. Run with no approved policy and verify status is `unassessed` with human review required.
5. Run a conflicting case and verify an evidence-backed escalation; no product recommendation is authorized.
6. Confirm parent session identity and unrelated Aria routes are unchanged.

Do not configure a live OCR/KYC provider, AML threshold, or retention period until supplied and approved by the responsible owners.
