# Quickstart: Validating Profiles and Audit

Prerequisite: project virtualenv active (no extra packages needed).

1. **Validate profiles**: `python -m speckit_flow profiles validate` → all 8 profiles valid.
2. **Suggest**: `python -m speckit_flow profiles suggest "fix crash in statement parser"` → `bugfix`.
3. **Bugfix run**: `python -m speckit_flow init --profile bugfix --feature-dir specs/009-workflow-profiles-audit` on a scratch feature dir; `status` shows `plan` and `analyze` skipped with reasons.
4. **Enterprise run**: init with `enterprise`; every stage has a gate.
5. **Default**: `init` without `--profile` → `feature`, route and gates equal the current `workflow.yml`.
6. **Gate audit**: `stage start specify`, `stage done specify`, `gate approve specify`, then `gate reject plan`; `audit.jsonl` lists each event in order with increasing `seq`.
7. **Append-only**: edit a middle line of `audit.jsonl`; `status` reports a broken hash chain.
8. **Resume**: delete `state.json`; `resume` reports it missing and `rebuild` restores it from existing artifacts.
9. **Unknown profile**: `init --profile nope` lists valid profiles and exits non-zero.
10. **Tests**: `pytest tests/unit/speckit_flow -q`.

Expected outcomes follow [contracts/cli.md](./contracts/cli.md) and [data-model.md](./data-model.md).
