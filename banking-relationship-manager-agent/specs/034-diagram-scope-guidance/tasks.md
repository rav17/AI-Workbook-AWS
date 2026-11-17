# Tasks: Two-Level Diagram Scope Guidance

**Feature**: `specs/034-diagram-scope-guidance`  
**Route**: `refactor` (minimal); documentation-only  
**Inputs**: `specs/034-diagram-scope-guidance/spec.md` (Draft, read-only), `plan.md`, `data-model.md`, `quickstart.md`  
**Status note**: T001-T012 remain checked as the original documentation-only implementation tasks; their scope and historical evidence are not rewritten. In the separately authorized bounded implement resume, exactly one approved application-source line was changed at `speckit_flow/reviews.py:57` (see [implementation-evidence.md](implementation-evidence.md)), so the cumulative worktree is not documentation-only. No shared or feature-local diagram was changed, and no diagram validator was run. Preservation provenance and the existing 14-file SHA-256 evidence are documented there, but the ignored `.specify/feature.json` has no pre-resume fingerprint: whole-resume pointer preservation remains unverified, and the later fingerprint covers only its later interval. T004, T007, T010, and T011 are recorded implementation checks, not an independent review verdict. Fresh independent diff/hash measurements and this stage's configured lint/unit-test sensor results are pending; historical sensor/test reports are not substitutes. The support-reported broad pytest run is not feature-specific acceptance. This record does not imply specification approval or lifecycle-gate approval.

## Scope and task-time prohibitions

Authorized implementation scope was exactly these three documentation surfaces:

- `.github/skills/speckit-diagrams/assets/index-template.md`
- `.github/skills/speckit-diagrams/SKILL.md`
- New `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md`

Do not change `specs/034-diagram-scope-guidance/spec.md`, its checklist, feature 033, application/source files, any other feature-local user artifacts, or any of the 14 existing `docs/architecture/*.drawio` files. Do not copy shared baseline diagrams. This refactor does not require feature-local diagrams; do not create an empty `specs/034-diagram-scope-guidance/architecture/diagrams/` directory. Examples must be synthetic and contain no customer data or secrets. No diagram validator is needed for this refactor. Structural validation, if ever relevant to another feature, is not architecture approval.

## Phase 1: Setup — preservation baseline

**Purpose**: Establish a reproducible preservation checkpoint before separately authorized documentation edits. Task generation itself did not run this capture; the original implementation-session capture was later made before edits and is retained externally with provenance summarized in [implementation-evidence.md](implementation-evidence.md).

- [x] T001 Capture the complete path/count and SHA-256 baseline for `docs/architecture/*.drawio` before authorized edits; require exactly 14 paths. The original capture was retained outside the repository; its provenance and verified comparison to the post-edit/current inventories are summarized in [implementation-evidence.md](implementation-evidence.md) (FR-010, SC-005).

  Original capture command form (repository root):

  ```powershell
  $drawings = Get-ChildItem 'docs/architecture' -File -Filter '*.drawio' | Sort-Object Name
  if ($drawings.Count -ne 14) { throw "Expected 14 baseline diagrams; found $($drawings.Count)" }
  $drawings | ForEach-Object { "docs/architecture/$($_.Name) $((Get-FileHash $_.FullName -Algorithm SHA256).Hash)" }
  ```

  **Recorded result**: the original capture contains 14 sorted paths and SHA-256 values and precedes the successful documentation edit command in the retained event history. The supplied machine comparison and current recomputation match all 14 paths and hashes. The external record and limits are documented in [implementation-evidence.md](implementation-evidence.md).

## Phase 2: Foundational

No application setup, runtime model, API, or test infrastructure was required. T001 was the pre-edit preservation prerequisite; separate implementation authorization was required before editing and is not inferred by this task record.

## Phase 3: User Story 1 — Keep feature views local and baseline distinct (Priority: P1, MVP)

**Goal**: State the two-level ownership/location rule without requiring every candidate diagram; distinguish optional conceptual ideation sketches from approved architecture.

**Independent test**: Review the updated skill and register template for the shared `docs/architecture/` baseline, useful feature-local views only under `<feature-dir>/architecture/diagrams/` on the full-lifecycle route, no duplicated baseline, no mandatory view set, and optional/unapproved conceptual sketches. This story's review is not evidence that every future feature complies universally.

- [x] T002 [P] [US1] Update `.github/skills/speckit-diagrams/assets/index-template.md` with view applicability/status, navigable source references, and rationale when deferred or not applicable; ensure the register does not require every candidate view or a baseline copy (FR-001, FR-002, FR-004).
- [x] T003 [P] [US1] Update `.github/skills/speckit-diagrams/SKILL.md` to distinguish solution-wide baseline ownership from useful full-lifecycle feature-local views, keep ideation sketches explicitly optional and conceptual, and state that no feature diagrams are imposed on non-applicable routes (FR-001, FR-002, FR-003, FR-009, FR-010).
- [x] T004 [US1] Review the completed US1 changes in `.github/skills/speckit-diagrams/assets/index-template.md` and `.github/skills/speckit-diagrams/SKILL.md` against both US1 acceptance scenarios and FR-001–FR-004; verify examples/instructions do not imply mandatory candidate views, copies, or approved sketches (SC-001).

  **Review check**: `git diff --check -- .github/skills/speckit-diagrams/assets/index-template.md .github/skills/speckit-diagrams/SKILL.md`; then manually inspect both complete files against the criteria above. Whitespace success alone is not functional acceptance.

**Checkpoint**: US1 is independently reviewable; only then proceed to US2. T002 and T003 may run in parallel after T001 because they touch different files.

## Phase 4: User Story 2 — Relate feature views to relevant baselines (Priority: P1)

**Goal**: Link relevant baselines with context and make missing, stale, conflicting, or uncertain source evidence auditable without fabricated links or alignment claims.

**Independent test**: Inspect the register and procedure for relevant, irrelevant, missing, stale, conflicting, unknown-source-version/status, and unknown-review-point cases. Confirm pending missing-baseline owner disposition asserts neither relevance nor a link. This focused review does not establish universal 100% future compliance (SC-001, SC-004).

- [x] T005 [P] [US2] Extend `.github/skills/speckit-diagrams/assets/index-template.md` with FR-005 relative baseline link plus relevance and feature-specific scope/differences, and the FR-006 review record: baseline identifier or explicit missing status; timezone-aware reviewed-at time; reviewer identity/role and designated-owner status; each relevant source ID and version/revision; explicit uncertainty and revalidation request for unknown version/status or review point; gap/conflict and owner revalidation request; and, for missing baseline, owner disposition (pending/relevant/not relevant), follow-up, and rationale (FR-005, FR-006).
- [x] T006 [P] [US2] Update `.github/skills/speckit-diagrams/SKILL.md` to require evidence-based source/review claims, define stale as a relevant source superseded or changed since the recorded review, require designated-owner review/revalidation for missing/stale/conflicting baselines, and prohibit asserting relevance or a link while missing-baseline disposition is pending or fabricating a baseline link (FR-005, FR-006).
- [x] T007 [US2] Review the updated `.github/skills/speckit-diagrams/assets/index-template.md` and `.github/skills/speckit-diagrams/SKILL.md` against relevant/no-relevant/missing/stale/conflict/unknown cases; verify every FR-006 field and that unknown evidence is explicitly uncertain rather than verified (FR-005, FR-006; SC-001, SC-004).

  **Review check**: `git diff --check -- .github/skills/speckit-diagrams/assets/index-template.md .github/skills/speckit-diagrams/SKILL.md`; use `rg -n "baseline|reviewed|revision|uncertain|revalidation|pending|relevant|not relevant|stale|conflict"` on those exact paths as a navigation aid, then manually check semantics and the cases above. Search hits alone are not acceptance evidence.

**Checkpoint**: US2 review passes before shared-change proposal work. T005 and T006 may run in parallel after US1 because they edit different files; T007 follows both.

## Phase 5: User Story 3 — Review proposed shared-architecture changes (Priority: P2)

**Goal**: Require a recorded designated-owner decision before applying any shared-view change, with conditional approval strictly sequenced; distinguish structural checks from architecture decisions.

**Independent test**: Review the proposal template and skill procedure for pending, rejected, conditional, condition-satisfied-but-not-yet-approved, and explicitly approved cases. Verify no outcome other than subsequent explicit owner approval after every condition is evidenced and before application permits the change. Verify validator results are described only as structural.

- [x] T008 [P] [US3] Create `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md` with affected baseline view, rationale, expected impact on other features/views, designated owner identity/role, outcome, conditional terms, evidence every condition is satisfied, and a subsequent explicit owner approval record (FR-007, FR-008).
- [x] T009 [P] [US3] Update `.github/skills/speckit-diagrams/SKILL.md` to state pending/rejected/conditional outcomes block application; satisfying conditions alone is not approval; explicit owner approval must follow recorded satisfaction and precede application; structural XML/graph validation is not correctness, completeness, security, or approval; and examples remain synthetic/no customer data or secrets (FR-007, FR-008, FR-009).
- [x] T010 [US3] Review `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md` and `.github/skills/speckit-diagrams/SKILL.md` against all US3 scenarios and the approval sequence; confirm no owner or approval is inferred and validator success cannot authorize application (FR-007, FR-008; SC-002, SC-003).

  **Review check** (also covers a new, untracked proposal template):

  ```powershell
  $paths = @('.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md', '.github/skills/speckit-diagrams/SKILL.md')
  foreach ($path in $paths) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing $path" }
    $lineNumber = 0
    Get-Content -LiteralPath $path | ForEach-Object { $lineNumber++; if ($_ -match '[\t ]+$') { throw "Trailing whitespace: $path line $lineNumber" } }
  }
  git diff --check -- .github/skills/speckit-diagrams/SKILL.md
  ```

  **Pass**: both files exist, no trailing-whitespace exception occurs, tracked changes pass `git diff --check`, and a reviewer manually traces every outcome state and sequence. A structural validator cannot substitute for owner authorization.

**Checkpoint**: US3 is reviewable only after US2. T008 and T009 may run in parallel after US2 because they touch different files; T010 follows both. Shared-view application remains blocked unless the designated architecture owner records the required explicit approval.

## Final Phase: Polish and cross-cutting verification

- [x] T011 Review the three implemented surfaces `.github/skills/speckit-diagrams/assets/index-template.md`, `.github/skills/speckit-diagrams/SKILL.md`, and `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md` against every requirement FR-001–FR-010 and outcome SC-001–SC-005; verify scope boundaries, synthetic examples, all review/proposal fields, and truthful validator limitations. Confirm all three exist, run the whitespace check below, and manually inspect full content. Representative scenarios do not prove universal future compliance.

  ```powershell
  $paths = @('.github/skills/speckit-diagrams/assets/index-template.md', '.github/skills/speckit-diagrams/SKILL.md', '.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md')
  foreach ($path in $paths) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing $path" }
    $lineNumber = 0
    Get-Content -LiteralPath $path | ForEach-Object { $lineNumber++; if ($_ -match '[\t ]+$') { throw "Trailing whitespace: $path line $lineNumber" } }
  }
  git diff --check -- .github/skills/speckit-diagrams/assets/index-template.md .github/skills/speckit-diagrams/SKILL.md
  ```

  **Pass**: all three files exist; the whitespace scan returns no error; tracked-file `git diff --check` passes; and the manual FR/SC trace succeeds. The existence/whitespace checks and representative review cases do not prove universal future compliance.
- [x] T012 After authorized documentation edits, compare the retained post-edit inventory and `git status --short -- docs/architecture` with T001; require exactly 14 identical sorted paths and SHA-256 values and no diagram status entries. The original exact comparisons and their provenance are retained externally; the recovery-time current inventory independently matches them (FR-010, SC-005).

**Final checkpoint**: Documentation review (T011) and exact path/hash/status preservation evidence (T012) pass before implementation work is reported complete. No diagram validator is run for this refactor because no feature-local diagram is created or changed.

## Dependencies and execution order

- T001 was the mandatory pre-edit preservation checkpoint; the authorized edit tasks followed it.
- US1 (T002/T003 in parallel; then T004) precedes US2 (T005/T006 in parallel; then T007), which precedes US3 (T008/T009 in parallel; then T010).
- T011 and T012 are final checks and depend on all authorized implementation tasks; T012 must compare against T001.
- No task creates/updates diagrams, modifies feature 033, changes application code, or runs a diagram validator.

## Verification and evidence boundary

T004, T007, T010, and T011 were completed as documentation acceptance reviews; their checks and manual findings are recorded in [implementation-evidence.md](implementation-evidence.md). These are not feature-specific automated tests. The support-reported broad project pytest run did not target this documentation feature and is not acceptance evidence. No diagram validator was run because no diagram changed and this is a `refactor` route. The quickstart's path/hash command is preservation evidence only; it does not prove architecture correctness, completeness, security, or owner approval. SC-001, SC-002, and SC-004 describe universal future behavior; representative review cases can find defects but must not be reported as proof of universal compliance. The spec remains Draft; no spec approval is inferred.