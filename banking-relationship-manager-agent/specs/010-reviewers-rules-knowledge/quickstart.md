# Quickstart: Validating Reviews, Rules, Knowledge, Composer, Stages

Prerequisite: 009 tooling working (`python -m speckit_flow profiles validate`). Use a scratch feature directory.

1. **Regression**: `pytest tests/unit/speckit_flow -q` passes, including all 009 tests (SC-006).
2. **New stages**: `profiles validate` accepts `full-lifecycle` (ideation to operate); a profile with `operate` but no `deploy` is rejected.
3. **Review citations**: `review save specify --file good.json` succeeds; the same file with a finding missing `section` is rejected; a finding citing a nonexistent file is rejected.
4. **Verdict rules**: a `blocker` finding with verdict `pass` is rejected; `reviewer` equal to `author` is rejected.
5. **Gate coupling**: with a `block` review, `gate approve specify` is refused; with `--override-reason "accepted risk, tracked in X"` it succeeds and the audit trail shows `gate_overridden` and `review=<id>`.
6. **Comprehensive depth**: on an `enterprise` feature, `gate approve` without a review is refused.
7. **Staleness**: edit a reviewed file; `review list` shows the review stale and approval is refused at comprehensive depth.
8. **Rules**: `rules propose --manual --text "Specs MUST name the compliance owner"` stores `pending`; `rules list --stage specify` does not show it; `rules approve R-001 --actor agent:x` fails; with `--actor human:me` it succeeds and the rule now appears for `specify`.
9. **Rule redaction**: proposing text containing `AKIA...` is rejected.
10. **Knowledge**: `knowledge list --stage plan` lists starter documents; with an empty folder it reports none found.
11. **Composer**: `compose validate --file route.json` rejects an invalid route naming the broken rule; `compose save --confirm` writes `route.json`, initializes state and audits `route_composed`.
12. **Audit integrity**: `status` still verifies the hash chain after all of the above.

Expected outcomes follow [contracts/cli.md](./contracts/cli.md) and [data-model.md](./data-model.md).
