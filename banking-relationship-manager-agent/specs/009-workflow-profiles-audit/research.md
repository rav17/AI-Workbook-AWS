# Research: Workflow Profiles and Audit Trail

Source: [awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows) docs (introduction, workflow profiles, phases and stages).

## D1: Profile model
- **Decision**: A profile = `{id, description, stages[], depth, gates[], skip_reasons}` where stages are a subset of Spec Kit stages: `specify, clarify, plan, tasks, analyze, implement`.
- **Rationale**: AI-DLC "scopes" fix route, depth, test strategy and ceremony per kind of work. Phase 1 maps this to the stages Spec Kit already has.
- **Alternatives**: copy all 33 AI-DLC stages (rejected: out of scope, later phases); hard-code in workflow.yml (rejected: FR-005 needs editable config).

## D2: Profile format
- **Decision**: JSON files in `.specify/profiles/`, validated by code and a JSON Schema.
- **Rationale**: stdlib parsing, no new dependency; PyYAML is not guaranteed in the Spec Kit environment.
- **Alternatives**: YAML (rejected: dependency), Python modules (rejected: not editable without code).

## D3: Initial profiles
| Profile | Stages | Depth | Gates |
|---|---|---|---|
| feature (default) | specify, plan, tasks, implement | standard | after specify, after plan |
| enterprise | specify, clarify, plan, tasks, analyze, implement | comprehensive | after every stage |
| express | specify, tasks, implement | minimal | after specify |
| bugfix | specify, tasks, implement | minimal | after specify |
| refactor | specify, plan, tasks, implement | minimal | after plan |
| infra | specify, plan, tasks, implement | standard | after plan |
| security-patch | specify, tasks, implement | minimal | after specify |
| poc | specify, implement | minimal | none |

`feature` equals the current `workflow.yml` route and gates (FR-004, SC-002). Route rule: `implement` requires `tasks`, except `poc` which has a declared exemption; `plan` requires `specify`.

## D4: State and audit storage
- **Decision**: `state.json` (authoritative, atomic temp-file replace) plus rendered `state.md`; `audit.jsonl` one JSON object per line, opened in append mode only.
- **Rationale**: human readable, diffable, version-controlled (FR-012). JSONL gives cheap append-only semantics. Each event carries `seq` and the previous event's hash so tampering is detectable.
- **Alternatives**: markdown audit (harder to validate), SQLite (opaque in git).

## D5: Integration with Spec Kit
- **Decision**: a `speckit-profile` skill does selection, confirmation and switching; the workflow engine passes `profile` to it and wraps each step with `stage start/complete` calls to the CLI.
- **Rationale**: the project instructions mandate Spec Kit skills; skills are the supported extension point.
- **Risk**: workflow.yml schema may not allow shell steps. Fallback: the skill instructions tell the agent to call the CLI at stage boundaries. To be verified in implementation.

## D6: Profile suggestion
- **Decision**: deterministic keyword scoring (e.g. "bug", "fix", "CVE", "terraform", "refactor"), advisory only; the human confirms.
- **Rationale**: testable and offline. An LLM composer is a later phase.

## D7: Redaction
- **Decision**: reject event free-text matching common secret patterns (AWS keys, bearer tokens, long hex/base64 strings, account-number-like digit runs) with a clear error.
