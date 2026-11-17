# Plan: lean workflow validation

## Approach

Keep the current CLI and workflow. Reuse the shared task parser for duplicate
validation and reject empty trace inputs explicitly. Include unknown_refs in
TraceMatrix.ok and downstream failure diagnostics; orphan setup tasks remain
advisory. Trace remains planned coverage, not executed test evidence.

Add a constant-memory audit snapshot carrying count, parked status and integrity
problem from one streaming read. Reuse the chain-checking implementation rather
than caching or weakening it. Context and dispatch use the snapshot; existing
read_events and is_parked APIs remain available to unrelated callers.

Edit the existing plan template only: remove generic architecture option trees,
retain actual-structure instructions and conditional ancillary artifacts.
Retain required technical context, constitution and complexity sections.
Quick consolidation does not apply to richer profiles' required documents.

## Affected files

speckit_flow/audit.py, cli.py, orchestration.py, trace.py, sensors.py and state.py;
focused audit/context/orchestration/trace/sensor/gate tests; plan template and
docs/speckit-profiles.md. Existing portable bundle already includes these files.

## Project practices and validation

Root: banking-relationship-manager-agent.
Practices fingerprint: fbc67b2038985355d110429bd692be8683bbd463d79b93770f5c40098c4f6e08.
Python/pytest/Ruff/mypy from pyproject.toml and existing engine tests. Preserve
constitution's deterministic state, explicit failures and bounded-context rules.
No dependencies, services, production data or changes to domain architecture.

Commands from project root:
- python -m pytest tests/unit/speckit_flow -q
- python -m pytest tests/unit/test_speckit_bootstrap.py::test_install_is_portable_and_target_doctor_passes -q
- python -m ruff check speckit_flow scripts
- python -m mypy speckit_flow/audit.py speckit_flow/cli.py speckit_flow/orchestration.py speckit_flow/trace.py speckit_flow/sensors.py speckit_flow/state.py --follow-imports=silent

Measure audit file-open count with an instrumented test: exactly one each for
context and dispatch, including large valid histories and parked/tampered cases.
Measure plan-template bytes before/after; require at least 25 percent reduction.
Run focused tests first, then lifecycle/portability and configured implementation
sensors. Disclose unrelated failures instead of modifying unrelated application
code. No independent review is configured for quick.

## Research applied

- Claude Code best practices: enforce non-negotiable checks; concise relevant
  instructions, not ever-longer prompts:
  https://code.claude.com/docs/en/best-practices
- Kiro: requirements/design/tasks as core artifacts:
  https://kiro.dev/docs/specs/
- AI-DLC: risk-adaptive profiles rather than every stage for every change:
  https://github.com/awslabs/aidlc-workflows/blob/main/docs/guide/workflow-profiles.md
- Upstream Spec Kit template retains generic layouts; our local adaptation
  intentionally removes unused examples rather than importing more ceremony:
  https://github.com/github/spec-kit/blob/main/templates/plan-template.md

## Risks and exclusions

Stricter traces intentionally reject previously accepted bad inputs. A smaller
template must still preserve mandatory policy. One audit snapshot is fresh per
call, not permission to reuse it across state changes or later invocations.
No removal of recorded questions, automatic human answers, broad policy
deduplication, subagent trial, or changes to the previously implemented units.

## Verified outcome

- Lifecycle suite plus portable installation smoke test: 505 passed, 8 skipped
  in 90.24 seconds. Skips cover unavailable Windows symlink creation and
  unavailable optional specify_cli integrations, not accepted failures.
- Required implementation sensors: lint and full tests/unit both exited 0.
  Their runner intentionally does not store test output; no full-suite count
  is inferred from that exit status.
- Ruff passed for the engine, scripts and all six changed test files.
  Mypy passed all six changed engine files. git diff --check passed.
- Instrumented context and dispatch calls each open the audit file exactly
  once (previously three times). A 2,000-event snapshot opens once too;
  park/resume freshness, chain corruption, invalid encoding and permission
  failures are covered. No persistent cache was introduced.
- Template: 3,682 to 2,573 bytes, a 30.12 percent reduction, exceeding the
  required 25 percent. Regression tests retain mandatory sections and
  conditional quick-only ancillary artifacts.
- Required-test gate regressions reject unknown references, empty task sets
  and duplicate IDs without clearing the human gate. Trace validation also
  rejects empty requirement sets; valid setup/orphan tasks remain advisory.
- Graphify AST-only update succeeded; no LLM labeling or semantic extraction
  was run. Existing generated-graph changes were preserved.
- No extra workflow stages, agents, human gates, dependencies, commits or
  deployment actions. Custom conductor dispatch is still not host-verified;
  this change does not make that claim or change the prior trial's scope.

The local read-count and template-byte reductions are measured; end-to-end
latency, tokens/cost and comparison with Kiro/Claude Code are not benchmarked.
Final completion edits change artifact fingerprints; refresh the configured
implementation sensors after saving this evidence and tasks, before closing
the lifecycle. Do not edit the three core artifacts after that refresh.
