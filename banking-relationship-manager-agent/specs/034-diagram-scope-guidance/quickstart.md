# Quickstart: Review and Verify Diagram-Scope Guidance

This is a future documentation-review guide for the implementation stage. It does not authorize or perform implementation during plan, and it does not claim that any check has already run.

## Prerequisites

- Treat `specs/034-diagram-scope-guidance/spec.md` as a read-only, draft-status input and leave it and the checklist unchanged. The specify stage being recorded done does not establish a direct human approval event; do not describe the spec as approved without verifiable provenance.
- Use synthetic information only; do not add customer data or secrets.
- Keep the 14 existing `docs/architecture/*.drawio` files byte-for-byte unchanged. Do not add, delete, regenerate or copy baseline diagrams.
- This `refactor` feature does not require feature-local diagrams. Do not create an empty `specs/034-diagram-scope-guidance/architecture/diagrams/` directory.

## Review guidance content

Compare future guidance changes to FR-001 through FR-010 and SC-001 through SC-005 in [spec.md](spec.md). Inspect the committed future implementation surfaces `.github/skills/speckit-diagrams/assets/index-template.md`, `.github/skills/speckit-diagrams/SKILL.md`, and the new `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md`; these paths are acceptance targets only and were not changed during plan. Confirm that:

1. The shared baseline and feature-local useful views have distinct ownership and paths; the guidance does not require every candidate view.
2. A feature register uses relative links for relevant baseline views and explains relevance plus feature-specific scope/differences. For a missing baseline, do not assert a link or relevance until the designated architecture owner determines relevance; no fabricated link is required.
3. Missing, stale, conflicting or uncertain baseline/source evidence is recorded with its sources and a designated-owner review/revalidation request; it is never presented as verified or aligned without evidence. For a missing baseline, the designated architecture owner reviews the gap, determines whether a shared baseline is relevant and what follow-up is appropriate, and records that disposition; no baseline link is asserted before relevance is determined, and no fabricated link is required.
4. The feature-register template provides an FR-006 baseline-review record with baseline view identifier (or explicit missing status), timezone-aware reviewed-at date/time, reviewer identity and role, designated-owner status, each relevant source ID and version/revision, explicit uncertainty for unknown source version/status, and gap/conflict plus owner revalidation request. For a missing baseline, include owner disposition (pending / relevant / not relevant), appropriate follow-up, and rationale; while pending, assert neither relevance nor a link. The skill requires the designated architecture owner to determine and record missing-baseline relevance, appropriate follow-up, and rationale. Until that disposition exists, neither relevance nor a link is asserted; no fabricated link is permitted.
5. The shared-change proposal template provides FR-007/FR-008 fields for affected view, rationale, expected impact on other feature views/features, designated owner identity/role, outcome, conditions, evidence every condition is satisfied, and subsequent explicit owner approval. Verify sequencing: pending/rejected/conditional block application; satisfying conditions alone does not approve; explicit owner approval is recorded after condition satisfaction and before application. Structural validation is never authorization. No owner or approval is inferred.
6. XML/graph structural validation is described only as structural validation, never as architecture correctness, completeness, security or approval.
7. Examples are synthetic and contain no customer data/secrets. FR-006 concerns architecture review, not transaction audit.
8. The draft-status spec and checklist remain unchanged; no approval is inferred and no feature 033 files are changed.

## Baseline preservation check (run before and after future documentation edits)

In PowerShell at repository root, capture the complete path/count and SHA-256 list before editing and repeat after editing:

```powershell
$drawings = Get-ChildItem 'docs/architecture' -File -Filter '*.drawio' | Sort-Object Name
"count=$($drawings.Count)"
$drawings | ForEach-Object { "{0} {1}" -f $_.Name, (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
```

Compare both outputs: the current inventory is 14 and the after-edit path list and each hash must match the before-edit output exactly. A matching count alone is insufficient because a file could have been replaced. Also review `git status --short -- docs/architecture` for unexpected additions/deletions/modifications; the hashes/path comparison is the preservation evidence.

## Diagram validator applicability

No feature-local diagrams are required or created for this refactor, so do not run the diagram validator merely to imply diagram approval. If a later applicable full-lifecycle task actually changes a feature-local draw.io file, use the command documented in [speckit-profiles.md](../../docs/speckit-profiles.md):

```powershell
python -m speckit_flow diagrams validate --feature-dir <feature-dir>
```

A pass covers XML and graph references only. It does not establish architectural correctness, completeness, security, or owner approval. Any shared-view change remains blocked until its recorded explicit owner approval, regardless of validator result.

## Expected outcome

A reviewer can trace applicable feature views to identified baseline evidence when relevance and review status are established, record missing or uncertain cases without fabricated links, distinguish structural checks from architecture decisions, and verify that the solution-wide diagram inventory and file bytes did not change. This guide describes future acceptance checks only; it is not test execution evidence or gate approval. The specification remains `Draft`; stage completion or this plan does not establish specification approval, and no separate approval is claimed.
