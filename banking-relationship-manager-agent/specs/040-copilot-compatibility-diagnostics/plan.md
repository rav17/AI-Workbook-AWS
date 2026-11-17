# Implementation Plan: Copilot Compatibility Diagnostics

**Branch**: Not created | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

**Input**: Confirmed narrow quick inline correction; tasks human gate.

**Limit**: No enforcement changes, independent review or live-host certification.

## Summary

Clarify the conductor's existing worker execution contract. Distinguish declared
tool restrictions, observed capability failures and unavailable runtime evidence.
A missing per-call tool override alone cannot establish that restrictions are
unsupported. Unverified required enforcement remains a reason to stop, with a
precise explanation of missing evidence rather than an unsupported root cause.

## Technical Context

- Markdown instructions and Python 3.11+ pytest instruction-contract checks.
- No dependencies, storage, hook payloads, worker tools or public APIs change.
- Only the conductor body, related profile guidance and existing test file change
  outside feature artifacts.
- No expected runtime performance impact; no new permission implementation.

## Constitution Check

Pre-design and post-design: applicable principles pass for this narrow scope.
Prompts do not replace deterministic authorization. No enforcement, human
decision automation or trust settings change. Existing dirty worktree content
is preserved. Focused tests validate the instruction contract, not host isolation.

## Evidence and Design Decisions

Observed ambiguity: the conductor body at
`.github/agents/speckit-conductor.agent.md:29` requires restricted worker tools
but does not distinguish an absent per-call override from unsupported configured
restrictions. The interrupted continuation reported inability to verify the
restriction through the invocation interface. This supports correcting the
diagnostic ambiguity, not concluding that this host ignores restrictions.
Raw host logs were not accessed.

Official references consulted on 2026-11-17:

- [GitHub custom-agent tools](https://docs.github.com/en/copilot/reference/custom-agents-configuration#tools):
  configured tool lists select available agent tools.
- [VS Code custom-agent reference](https://code.visualstudio.com/docs/agents/reference/custom-agent-file-reference#tools):
  tool support depends on the harness.
- [Conversion limits](https://code.visualstudio.com/docs/agents/reference/custom-agent-file-reference#copilot-specific-configuration):
  `strict-tools-list` is not forwarded during SDK agent conversion.

Documentation evidence is not runtime evidence about this session.

Chosen implementation:

1. Extend the existing conductor contract with precise diagnosis distinctions,
   retaining original stop language and frontmatter unchanged.
2. Document the same distinctions in the profile guide's host setup section;
   cross-reference it from the later worker-execution guidance.
3. Extend the existing instruction-contract tests to cover these distinctions
   and preserved stop conditions.

Rejected/out of scope: adding hooks, disabling restrictions, generic substitution,
claiming worker summaries or lack of observed nesting prove enforcement, and
requiring a nonexistent invocation parameter. Unverified required enforcement
still stops work; it is not an implicit permission to continue.

## Project Practices

Project root: `banking-relationship-manager-agent`.
Practices fingerprint from `codebase practices --json`:
`7991a8ad9448a559fcca3356e346903c6f4069ac4231fba6af5b8c6fb698c5fc`.

Relevant sources were read:
`pyproject.toml:46` (pytest test paths/imports), `pyproject.toml:51` (Ruff),
`.github/workflows/quality.yml:35` (formatting/lint) and `:41` (pytest).
Existing regression prior art:
`tests/unit/speckit_flow/test_flow_orchestration.py:560` reads conductor text and
parses worker frontmatter with the existing parser. Reuse that test style.
The fingerprint identifies sources only, not passing validation. No baseline
test has run for this feature.

## Project Structure

### Documentation (this feature)

Core artifacts: `spec.md`, checklist, this plan, then `tasks.md`.
Separate research/data-model/contracts/quickstart files are intentionally omitted
under quick: no new entities, interfaces or runtime flows.

### Source Code (repository root)
- `.github/agents/speckit-conductor.agent.md`: body only, not tool declarations.
- `docs/speckit-profiles.md`: host diagnostic guidance only.
- `tests/unit/speckit_flow/test_flow_orchestration.py`: focused contract checks.

Guards, roster, profiles, engine permissions and feature 039 remain untouched.
The active pointer identifies feature 040; resuming 039 later uses its explicit
path rather than silently switching its route.

## Verification Scope Proposed for Human Approval

Run from the project root:

```powershell
python -m pytest tests\unit\speckit_flow\test_flow_orchestration.py -q
python -m ruff check tests\unit\speckit_flow\test_flow_orchestration.py
python -m ruff format --check tests\unit\speckit_flow\test_flow_orchestration.py
```

Run configured stage sensors through `speckit_flow sensors run`; report their
wider scope/failures separately rather than making unrelated fixes. Run
`graphify update .` after code/test changes; this is not live-host validation.

| Requirement | Check |
|-------------|-------|
| FR-001, FR-002 | New diagnostic contract checks and matching docs review |
| FR-003, FR-004 | Preserved-stop assertions and existing rooted-command/worker-tool test; scoped diff |
| FR-005 | Targeted pytest/Ruff and profile guide review |
| FR-006 | Final report states live enforcement unverified and 039 not unblocked |

## Risks and Limitations

- Tests assert written instructions, not LLM obedience or runtime permissions.
- No live smoke test is authorized by this correction.
- Preserve earlier uncommitted changes; inspect the delta against the read
  baseline, not just against HEAD.
- Listed banking knowledge is unrelated to this correction and is not changed.
- Quick provides no independent review; tasks is its human checkpoint.
