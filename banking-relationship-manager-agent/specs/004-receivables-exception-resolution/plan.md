# Implementation Plan: Virtual Account Receivables Exception Resolution Subagent

**Branch**: `004-receivables-exception-resolution` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification in `specs/004-receivables-exception-resolution/spec.md`

## Summary

Add one receivables exception specialist as a child Strands Agent exposed through Aria's existing parent. Use read-only payment, virtual-account, customer, invoice, and approved-procedure sources; perform matching, variance, eligibility, and duplicate validation in deterministic code; require an analyst decision before the only permitted case-management task write.

## Technical Context

**Language/Version**: Python 3.11 application; existing AgentCore Runtime remains Python 3.13.

**Primary Dependencies**: Existing `strands-agents==1.34.1`, Pydantic, boto3, pytest, and Hypothesis; no new Runtime or orchestration framework.

**Storage**: Mock/de-identified source fixtures and an injected append-only audit sink for the MVP. A case-task writer is the only write adapter and is callable only after an analyst approval state.

**Testing**: pytest, Hypothesis for monetary/date/duplicate invariants, fake source connectors, contract tests for the child-agent handoff and approval gate, and labelled evaluation fixtures.

**Target Platform**: Existing authenticated Aria parent/AgentCore Runtime with test-only source connectors and a controlled analyst demo interface.

**Project Type**: Python agent capability, deterministic decision-support workflow, and approval interface.

**Performance Goals**: Not specified by the source. Bound source calls with timeouts; measure investigation and analyst-decision latency in the MVP evaluation without inventing a target.

**Constraints**: One customer, one currency, and three exception classes; all source reads are read-only; tolerance/procedure/confidence values require owner approval; no autonomous financial action or master-data mutation.

**Scale/Scope**: One corporate customer and one currency over a labelled test set; invalid mapping, amount/reference mismatch, and suspected duplicate only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**PASS**: The Aria parent retains verified identity, tenant/session authority, and guardrail enforcement. The subagent receives a bounded exception request and can read only injected source interfaces. All amount, tolerance, eligibility, date, and duplicate decisions are deterministic. Payer/remittance text is untrusted data. The only write is an idempotent case-task action after analyst approval; no financial ledger or virtual-account mutation exists in the tool surface.

**External design gate**: Receivables/control owners must provide the approved operating procedure, tolerance table, matching policy, confidence threshold, access mapping, and labelled evaluation set before confident recommendations or case writes are enabled.

**Re-check after design**: Verify failed deterministic rules cannot be overridden by the model, low-confidence/conflicting/duplicate cases produce no recommendation, and only an approved analyst decision can invoke the case-task writer.

## Project Structure

### Documentation (this feature)

```text
specs/004-receivables-exception-resolution/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/investigation-and-approval.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)
```text
aria/agents/aria/receivables/
├── agent.py             # Specialist prompt, tool access, structured result
├── models.py            # Exception, evidence, recommendation, decision
├── sources.py           # Read-only source protocols and mock adapters
└── rules.py             # Deterministic eligibility, variance, duplicate rules
aria/agents/aria/         # Parent handoff registration
demo/receivables_exception/
├── app.py                # Analyst decision interface and mocked case writer
└── fixtures/             # One-customer, one-currency synthetic data
tests/unit/test_receivables_rules.py
tests/framework/test_receivables_subagent.py
tests/integration/test_receivables_approval.py
```

**Structure Decision**: Keep the specialist inside the existing Aria agent package and expose it to the parent through one bounded tool. Keep mock source adapters and the analyst approval interface in the local demo package. Do not create a new Runtime, CDK stack, generic write connector, or production deployment tier.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | One Aria specialist plus injected source/case adapters is sufficient for the bounded MVP. |
