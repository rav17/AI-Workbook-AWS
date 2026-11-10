# Implementation Plan: KYC/AML Verification Subagent

**Branch**: `006-kyc-aml-verification-subagent` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: UC3 KYC/AML subagent specification in `specs/006-kyc-aml-verification-subagent/spec.md`.

## Summary

Extend Aria with a bounded KYC/AML specialist capability using injectable document extraction and read-only verification providers. The specialist returns evidence-backed observations, deterministic field conflicts, policy-based risk findings when approved configuration exists, and human-review outcomes otherwise. No real provider, jurisdiction, threshold, or risk policy is selected by this plan.

## Technical Context

**Language/Version**: Python 3.11 application; existing AgentCore Runtime remains Python 3.13.

**Primary Dependencies**: Existing Strands, Pydantic, boto3, pytest, and Hypothesis; no new orchestration or OCR vendor dependency until owners select one.

**Storage**: In-memory/fake evidence for local tests; no raw identity documents in DynamoDB, AgentCore Memory, prompts, or ordinary logs.

**Testing**: pytest, Hypothesis for normalization/conflict invariants, fake document/source/policy providers, parent-subagent contract tests, and audit-redaction tests.

**Target Platform**: Existing Aria parent/AgentCore Runtime with mock-backed specialist integration; no separate Runtime.

**Project Type**: Python compliance decision-support specialist subagent.

**Performance Goals**: No source target specified. Add bounded provider timeouts and record stage latency; establish production SLOs only with provider measurements.

**Constraints**: Fail closed; source reads only; policy decisions are deterministic; model output cannot certify KYC or clear AML; human review for conflicts/policy gaps; support no real identifiers until retention/access are approved.

**Scale/Scope**: Generic typed extraction/verification contracts plus synthetic cases for document match, mismatch, missing source, AML alert, and unavailable policy. Document types and jurisdictions are configuration inputs, not hard-coded production support claims.

## Constitution Check

**PASS**: Parent Aria retains verified identity, tenant/session, safety, and final response authority. The child has no write-capable source adapter. Raw documents and secrets are excluded from Memory and logs. Deterministic code owns normalization, conflict comparison, and policy decisions. Missing providers/policies return incomplete/unassessed and escalate.

**External gate**: Compliance owners must approve jurisdictions/document fields, authoritative providers, source precedence, AML/risk indicators, thresholds, analyst roles, and retention before real data or production recommendations.

**Re-check after design**: Verify all child calls are parent-authenticated, source access is least-privilege/read-only, no data path persists raw documents, and fail-closed outcomes cannot be overridden by model text.

## Design Decisions

- Implement one Aria KYC/AML child specialist exposed through a bounded parent handoff; do not add a separate Runtime or identity system.
- Define protocols for document extraction, source verification, and approved compliance policy. Ship fake-backed fixtures only until contracts and credentials are provided.
- Normalize extracted fields and compare provider-sourced observations in deterministic code with explicit provenance and conflict outcomes.
- Do not invent a risk score. Without an owner-approved policy, assessment is `unassessed` and routed to human review.
- Keep the existing `KYCStatusProvider` and product gate fail-closed; adapt richer verification results into status only through a verified provider adapter.
- Redact/mask document values in outputs and audit; persist evidence references and safe summaries only.

## Project Structure

```text
aria/agents/aria/kyc_aml/
├── agent.py
├── config.py
├── models.py
├── providers.py
├── verification.py
├── policy.py
└── audit.py
aria/tools/compliance_tool.py         # Existing status gate plus typed provider protocol
aria/agents/aria/agentcore_entrypoint.py # Parent integration only after fake contract tests

tests/unit/test_kyc_aml_verification.py
tests/framework/test_kyc_aml_subagent.py
tests/property/test_kyc_aml_properties.py
```

**Structure Decision**: Keep document/compliance logic agent-specific; extend existing compliance contracts only where compatible. No OCR SDK, provider SDK, new storage, or deployment stack is added until selected by owners.

## Validation Gates

- Extraction/provider fakes validate missing, malformed, low-confidence, expired, matching, and conflicting observations.
- Deterministic verification and escalation are property/contract tested; model prompts cannot choose source precedence or statuses.
- Existing KYC product gating remains fail-closed for absent, timeout, malformed, and unknown provider responses.
- Tests inspect logs/audits to ensure raw IDs/document content/credentials do not leak.
- Parent handoff preserves tenant/session identity and does not alter unrelated Aria behavior.
- Live provider/OCR tests are not run until non-production contracts, credentials, access scopes, and retention approvals are supplied.

## Risks and External Dependencies

- The UC3 source does not identify document schema/jurisdictions, provider names, source precedence, AML/risk indicators, thresholds, or retention periods.
- Current Runtime construction has no authoritative KYC provider configured; real product recommendations therefore remain fail-closed.
- OCR/extraction can produce confident but incorrect fields; verification provenance and manual escalation remain required.

## Complexity Tracking

No new production service is justified before provider contracts exist; the MVP uses injected fake providers and one Aria child agent.
