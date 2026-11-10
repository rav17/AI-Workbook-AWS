# Implementation Plan: Profile-Aware Workflow Orchestration

**Branch**: Existing branch preserved | **Date**: 2026-11-10
**Spec**: [spec.md](./spec.md)

## Summary

Introduce one shared `speckit-workflow` entry skill for natural-language work
and direct stage commands. Add read-only recommendation and dispatch-preflight
CLI commands; use existing lifecycle transitions, sensors and human decisions.
Replace the static workflow with a host prompt that invokes this entry skill.
The host conductor invokes specialists; Python never pretends to execute models.

## Technical Context

- Language: existing Python 3.11+ engine and Markdown/YAML Copilot customizations.
- Dependencies: standard library only for new engine code; existing pytest,
  Ruff, mypy and optional installed Specify engine for tests.
- Storage: existing feature state/audit; no new execution database or credentials.
- Target: Windows and portable Copilot/Spec Kit receiving projects.
- Scope: routing and bounded dispatch, not autonomous deployment or new harnesses.

## Constitution Check

- Structured state remains authoritative; recommendation/preflight are read-only.
- Existing gates, verification approval and audit checks are reused.
- Request text is not persisted in routing results/audit.
- No live AWS or banking behavior changes; toolkit remains domain-neutral.
- Dispatch failure is explicit; regression tests cover guard conditions.
- Post-design check: passes; no governance exception needed.

## Design

1. Add `orchestration.py`: classify request intent with bounded keyword rules;
   return candidates/reasons and ask when ambiguous. Explicit profile wins.
   Clearly new features recommend full-lifecycle; hotfix uses bugfix.
2. `workflow recommend "<request>" [--profile <id>]` returns confirmation-required
   advice. No state mutation. Existing `profiles suggest` remains compatible.
3. `workflow dispatch [--stage <id>]` validates existing state/audit, park/gate,
   route order and roster/frontmatter/allowlist before producing a bounded
   lead/support/reviewer brief. It does not invoke models or mark work done.
4. Shared skill asks/records profile confirmation, allocates a feature folder
   before ideation when needed, initializes once, and invokes the conductor with
   feature/stage context. Existing initialized routes win over new suggestions.
5. Add a short handoff preamble to core stage skills. An explicit
   `SPECKIT_DELEGATED_STAGE=<stage>` conductor brief allows only the matching
   lead to execute the skill body; external calls delegate once and return.
   This is a recursion/context marker, not a security or approval token.
6. Conductor runs deterministic preflight, bounded supports, lead then independent
   reviewers; read-only supports return text, not files. It alone transitions
   stage state, runs sensors and stops at gates. Worker failure leaves work
   in progress; never report completion without host invocation evidence.
7. Standard YAML uses a prompt step invoking the skill. A session can end at a
   human gate; it is not feature completion. Existing in-flight engine cursors
   are not migrated. `speckit_flow resume` remains the lifecycle resume command;
   re-enter the session skill/workflow after actual human decisions.
8. Update workspace instructions and portable bundle/docs. Leave legacy
   `workflow begin --stages ... --gates ...` available for old explicit workflows.

## Project Structure

- Engine: `speckit_flow/orchestration.py`, `cli.py`, `agents.py`.
- Integration: `.github/skills/speckit-workflow/`, lifecycle skill preambles,
  `.github/agents/speckit-conductor.agent.md`, workspace instructions,
  `.specify/workflows/speckit/workflow.yml`.
- Distribution/docs: portable bundle allowlist and workflow/portability guides.
- Tests: new orchestration tests, affected workflow/profile/agent tests,
  portable acceptance.

## Verification

Proposed commands and host smoke checks are in [quickstart.md](./quickstart.md).
User approval is required before execution as a construction checkpoint.
Unit/engine dispatch mocks do not establish live model execution. A bounded
read-only host subagent smoke test will be reported separately.
