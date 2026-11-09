# Implementation Plan: Dispute Resolution Subagent

**Branch**: `005-dispute-resolution-subagent` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification in `specs/005-dispute-resolution-subagent/spec.md`

## Summary

Add one dispute-resolution specialist as a child Strands Agent of Aria. It gathers bounded evidence through mock read-only adapters, uses deterministic policy/rule code for eligibility and simulated actions, returns an explainable outcome, and routes uncertain cases to an analyst. No real card, refund, payment, account, ledger, or master-data action is implemented.

## Technical Context

**Language/Version**: Python 3.11 application; existing AgentCore Runtime remains Python 3.13.

**Primary Dependencies**: Existing `strands-agents==1.34.1`, Pydantic, boto3, pytest, and Hypothesis; no new Runtime or orchestration framework.

**Storage**: Mock/de-identified fixtures and injected source adapters; explicit workflow/recommendation/decision records and a correlated audit sink. Production persistence is not enabled by this MVP.

**Testing**: pytest, Hypothesis for monetary/policy invariants, fake read-only source adapters, subagent contract tests, approval-gate tests, and a labelled evaluation runner.

**Target Platform**: Existing authenticated Aria parent/AgentCore Runtime and a controlled local analyst demo using synthetic/de-identified records.

**Project Type**: Python decision-support specialist subagent and analyst review workflow.

**Performance Goals**: Not specified by the source. Bound source calls with timeouts and measure investigation/decision latency in the MVP evaluation without inventing SLO targets.

**Constraints**: One corporate customer, one currency, and two dispute categories; source reads are read-only; owner-approved policy is mandatory; all external actions are simulated; no production connector or financial mutation.

**Scale/Scope**: Labelled fixtures for fraudulent-transaction and merchant disputes only; no multi-customer or multi-currency support.

## Constitution Check

**PASS**: Aria remains the authenticated parent and holds verified tenant/session identity. The specialist gets one bounded case request. External text is treated as untrusted data. Deterministic code owns eligibility, thresholds, and variance. Human approval gates the only simulated case-task transition. No model tool can post to a ledger, block a card, issue a refund, return a payment, or mutate account/master data.

**External design gate**: Product/control owners must provide policy versions, action thresholds, allowed evidence fields, analyst roles, and labelled evaluation cases; absent values force human review.

**Re-check after design**: Confirm the child has only read adapters and a simulated action adapter, and that the latter cannot be invoked without an authorized human approval state.

## Design Decisions

- One dispute specialist uses explicit investigation stages (triage, evidence retrieval, deterministic validation, explanation, and handoff) inside one child agent; do not introduce an autonomous multi-agent swarm.
- Evidence access is dependency-injected through narrow read-only source protocols with mock/de-identified implementations.
- Rules and approved policy configuration determine eligible outcomes. The model may summarize evidence or propose a hypothesis, but cannot override rules or set thresholds.
- The local action adapter records simulated proposals only. The production action interface does not exist in the MVP.
- Human review state changes are explicit, versioned, and audited; future production writes require a separate reviewed feature.
- Payer/merchant/transaction strings pass through Aria guardrails and are never instructions.

## Project Structure

### Documentation

```text
specs/005-dispute-resolution-subagent/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/investigation-and-approval.md
├── checklists/requirements.md
└── tasks.md
```

### Source and Tests

```text
aria/agents/aria/dispute_resolution/
├── agent.py
├── models.py
├── sources.py
├── rules.py
├── approval.py
├── case_tasks.py
└── audit.py
aria/agents/aria/                 # Parent handoff registration

demo/dispute_resolution/          # Mock source/analyst interface only

tests/unit/test_receivables_rules.py
tests/unit/test_receivables_recommendations.py
tests/unit/test_receivables_approval.py
tests/framework/test_receivables_subagent.py
tests/evaluation/test_receivables_mvp.py
```

**Structure Decision**: Put specialist behavior in an Aria-specific package and keep source adapters/analyst demo behind injection. No new CDK stack, Runtime, generic write connector, or production app tier is justified by the bounded MVP.

## Validation Gates

- Deterministic tests cover mapping, scope, dates, currency, invoice eligibility, variance, tolerance, duplicate checks, and no-recommendation cases.
- Subagent tests prove Aria parent identity/session is preserved and external text cannot influence policy/tool authorization.
- Approval tests prove no case-task action before authorized approval; revise revalidates; reject/escalate never write; retries are idempotent.
- Audit tests prove each retrieval, rule, recommendation, analyst action, and simulated action has a correlated safe event.
- Labelled evaluation reports the PDF's accuracy, precision, escalation, evidence, and variance measures; policy values/labels require owner sign-off.
- No test path can call ledger/account/payment/virtual-account/master-data mutation.

## Risks and Open Decisions

- The repository contains no source API contracts, tolerance table, matching weights, action thresholds, analyst role mapping, or labelled dispute dataset. These are required inputs, not implementation defaults.
- The PDF's automated fraud example is represented as a test-only simulated outcome. Real card blocking/refunds require a separate authorization, compliance, operational, and integration review.
- Evaluation targets are provided, but dataset size, category labels, and ground-truth ownership must be agreed before acceptance.

## Complexity Tracking

No constitution exception or new production service is required; one child agent, deterministic rule module, and injected mock adapters are sufficient.
