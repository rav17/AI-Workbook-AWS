# Research: Reviewers, Rules, Knowledge, Composer, Extended Stages

Source: [awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows) docs (agents, rules and the learning loop, knowledge, scopes).

## D1: Reviewer model
- **Decision**: three roles (`spec`, `plan`, `code`) mapped to stages: spec reviewer for specify/clarify, plan reviewer for plan/tasks/analyze, code reviewer for implement, plus `deploy`/`operate` handled by the plan reviewer. The agent writes the review; code validates and saves it.
- **Rationale**: AI-DLC uses reviewer agents separate from authors with advisory findings at gates. Role separation is enforced by recording `reviewer` and `author` and rejecting equal values (FR-014).
- **Alternatives**: one generic reviewer (loses focus); LLM-only gating (not deterministic).

## D2: Source-bound evidence
- **Decision**: each finding has `file`, `section`, `severity` (`info|warning|major|blocker`), `note`; `file` must exist under the repo and be relative; the review stores a SHA-256 fingerprint over the reviewed files. A review is stale if any fingerprint no longer matches.
- **Rationale**: makes citations checkable and staleness visible (spec edge case).
- **Verdict rule**: any `blocker` finding forces verdict `block`; `pass` is invalid with major or blocker findings.

## D3: Gate coupling
- **Decision**: `gate approve` looks up the latest non-stale review for that stage. Depth `comprehensive`: review required. A `block` review needs `--override-reason`. Approval audit detail includes `review=<id>`; overrides emit detail `override: <reason>`.
- **Rationale**: FR-004, FR-005, FR-006. Minimal/standard depth: review optional, approval allowed without one.
- **Alternatives**: new `review_recorded` event type only (kept too, as `review_recorded`).

## D4: Learned rules
- **Decision**: `.specify/rules/rules.json` list of `{id, text, origin, status, proposed_at, decided_by}`. Proposals come from the skill via `rules propose --from-gate <stage>` or `--from-finding <review-id>:<n>`; status starts `pending`. Only a human actor can approve. Conflict check: two active rules with same normalized first-line key are flagged; the stricter (longer, containing MUST/NEVER) is shown first.
- **Rationale**: matches AI-DLC's learning loop with explicit human approval (FR-008, SC-003).
- **Alternatives**: auto-activation (rejected: violates spec).

## D5: Knowledge folder
- **Decision**: `.specify/knowledge/*.md`; each file may start with front matter-like lines `title:` and `stages:` (comma list or `all`). `knowledge list --stage X` returns titles and paths only (bounded context).
- **Rationale**: simple, no dependencies, bounded.

## D6: Composer
- **Decision**: agent proposes a route as JSON `{stages, depth, gates, reasons}`; `compose validate|save` reuses `Profile` validation (id `custom-<feature>`), writes `<feature>/route.json`, and audits `profile_selected` with `custom`. State init accepts `--route-file`.
- **Rationale**: single validation path (FR-011), stored with the feature (FR-012).

## D7: Extended stages
- **Decision**: stage order becomes `ideation, specify, clarify, plan, tasks, analyze, implement, deploy, operate`. Validation changes: `specify` must be first **except** that `ideation` may precede it; `deploy` requires `implement`; `operate` requires `deploy`. Existing profiles remain valid. A new `full-lifecycle` profile includes all stages. Artifacts: `ideation.md`, `release.md` (checklist, rollback), `runbook.md`, written by skills via templates in `.specify/templates/`.
- **Rationale**: FR-013, SC-006.
- **Risk**: data-model schema for stage names changes; JSON schemas updated accordingly and tests assert 009 profiles still validate.

## D8: Audit extensions
- **Decision**: new event types `review_recorded`, `gate_overridden`, `rule_proposed`, `rule_approved`, `rule_discarded`, `route_composed`. Hash chain unchanged, so 009 trails stay valid.
- **Rationale**: FR-015.
