# Implementation Plan: Two-Level Diagram Scope Guidance

**Branch**: `034-diagram-scope-guidance` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: The feature specification at `specs/034-diagram-scope-guidance/spec.md` is read-only for this stage and currently says `Status: Draft`. The specify stage is recorded done, but the permitted evidence does not establish a direct human approval event for the specification. Do not treat stage completion as specification approval. The provenance of any separate specification approval is not evidenced here; no fresh specify pass or approval is claimed.

## Summary

Establish governance guidance that keeps the solution-wide baseline in `docs/architecture/` distinct from useful, feature-local diagram views; links a feature view to a relevant baseline without copying it; records source/review uncertainty; and prevents any shared-view change absent the designated architecture owner's explicit recorded approval. Planning is documentation-only. The specification requires preserving all 14 existing solution-wide `.drawio` files. No feature diagrams are required for this `refactor` route.

## Technical Context

**Language/Version**: Markdown and draw.io XML guidance only; no application language change.

**Primary Dependencies**: Existing Spec Kit diagram skill, profile guidance, register template and structural validator; no new dependencies.

**Storage**: N/A. No application or persistent data store changes; records described by the guidance are governance artifacts, not a new runtime schema.

**Testing**: Future documentation review against FR-001 through FR-010 and SC-001 through SC-005; compare the exact baseline diagram path inventory and SHA-256 hashes before/after any allowed implementation work. No tests or validators were run during planning.

**Target Platform**: Repository documentation; no runtime platform.

**Project Type**: Documentation-only refactor.

**Performance Goals**: N/A.

**Constraints**: Do not edit `spec.md`, its checklist, the 14 existing `docs/architecture/*.drawio` files, feature 033, implementation artifacts, or guidance/docs/diagrams during this plan stage. Do not copy shared views into feature directories. No customer data or secrets in examples. Do not start tasks or implementation. The plan gate remains for human decision.

**Scale/Scope**: Guidance scope only; no API, application behavior, deployment, model, infrastructure, or customer data change.

## Constitution Check

**Before Phase 0**: PASS. This plan adds no transactional state, application authorization path, external call, logging/audit event, or customer-data processing. Documentation examples remain synthetic-only. No application code/test requirement is triggered by planning artifacts. The constitution's documentation and architecture-decision expectations are addressed by the explicit decisions and verification guidance below.

**After Phase 1 design**: PASS. The conceptual governance records are not a persisted application data model or customer-decision audit mechanism. No runtime contract or service selection is introduced. Human owner approval remains authoritative; structural validation is not authorization. No constitution exception or compensating test is needed.

## Project Structure

### Documentation (this feature)

```text
specs/034-diagram-scope-guidance/
|-- plan.md          # this plan
|-- research.md      # verified evidence and decisions
|-- data-model.md    # conceptual governance records; no runtime schema
`-- quickstart.md    # future review/verification guide
```

No `contracts/` directory is proposed: the feature exposes no API, CLI command, schema, or other external system interface. Later guidance implementation has required, traceable surfaces: `.github/skills/speckit-diagrams/assets/index-template.md` MUST add the FR-005 shared-baseline relative-link and relevance/scope-or-differences fields, and the FR-006 baseline-review field set; `.github/skills/speckit-diagrams/SKILL.md` MUST explain review evidence, uncertainty, and missing-baseline owner disposition; and a new `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md` MUST provide the FR-007/FR-008 proposal and outcome fields. These are future implementation commitments, not changes made in plan. No application source or draw.io diagram files are in the planned change set. `tasks.md` belongs to the later tasks stage and is not created here.

Future verification MUST inspect those exact surfaces: confirm the index template has the baseline link, relevance/scope, and review fields; confirm the skill requires the designated owner to record missing-baseline relevance, follow-up, and rationale before asserting relevance or a link; and confirm the proposal template records affected view, rationale, cross-feature impact, owner identity/role, outcome, conditional terms, condition-satisfaction evidence, and subsequent explicit approval. Confirm pending/rejected/conditional states block application, conditional approval follows recorded satisfaction, and structural validation is not authorization. These are acceptance criteria only; no implementation or test execution is claimed.

**Structure Decision**: Keep this planning output feature-local. Later implementation is documentation-only and includes the register template update stated above; it changes no application source or existing architecture diagram.

## Decisions and Rationale

1. **Keep the two-level scope boundary and provide an explicit register field.** Preserve `docs/architecture/` as the solution-wide baseline. Useful feature-specific views, if called for on a full-lifecycle route, remain in that feature's `architecture/diagrams/`; only relevant baseline views receive navigable relative links and a concise relevance / feature-specific scope-or-differences note. As a required implementation surface for FR-005, update `.github/skills/speckit-diagrams/assets/index-template.md` with a dedicated shared-baseline relative-link field and its relevance/scope-or-differences field. Do not duplicate the baseline or fabricate irrelevant links. A single shared-only model was rejected because it obscures feature-specific scope; per-feature copies were rejected because they create competing baseline sources.
2. **Make FR-006 baseline review evidence auditable through named guidance fields.** The future `.github/skills/speckit-diagrams/assets/index-template.md` MUST provide a baseline review record with: baseline view identifier (or explicit missing status); timezone-aware review date/time; reviewer identity and role; whether the reviewer is the designated architecture owner; each relevant source artifact identifier and version/revision; explicit uncertainty for any unknown source version/status; and gap/conflict plus owner revalidation request. For a missing baseline, include owner disposition (pending / relevant / not relevant), appropriate follow-up, and rationale; while pending, assert neither relevance nor a link. The skill MUST require recording sources and the designated owner's missing/stale/conflict review. For a missing baseline, the owner determines and records whether a shared baseline is relevant, appropriate follow-up, and rationale. Until that determination is recorded, assert neither relevance nor a baseline link and fabricate none. A directory listing or validator pass is not proof of freshness/correctness.
3. **Treat FR-007/FR-008 owner approval as a hard application gate with a proposal template.** The future `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md` MUST contain affected baseline view, rationale, expected impact on other features/views, designated owner identity/role, outcome (pending/rejected/conditional/explicitly approved), conditional terms, evidence that every condition is satisfied, and a subsequent explicit owner approval record. The skill MUST state that pending, rejected, and conditional outcomes block application; condition satisfaction alone does not approve; the owner records explicit approval after satisfaction and before application. Structural validation is separate and cannot authorize a change. Informal consensus, a conditional outcome alone, or validator success as approval were rejected (FR-007 through FR-008, SC-002 through SC-003).
4. **Preserve all 14 shared diagrams.** Current inventory is 14 files. Implementation must retain their exact path set and byte contents; use before/after hashes and path/count comparison as evidence. Editing or regenerating any baseline view, even to make an example look consistent, is outside this refactor (FR-010, SC-005).
5. **No feature-local diagrams for this route.** The current profile is `refactor`, whose route excludes the `full-lifecycle` diagram workflow. This feature changes governance guidance only; it creates no speculative or empty diagrams and does not copy shared views. Full-lifecycle feature authors may link to relevant baseline views in their own register per the guidance.
6. **No runtime model/contracts.** Record the spec's domain terms as conceptual governance records, not Pydantic entities or persistent transaction state. No external interface exists, so API/CLI contracts would be invented and are omitted.
7. **Use synthetic examples only.** No customer or secret data is needed (FR-009 and banking-compliance knowledge). This feature does not create a transaction audit obligation; FR-006 is about architecture baseline review traceability.

## Input Metadata and Evidence

The `spec.md` and checklist are read-only inputs. The spec says `Status: Draft`; the specify stage is recorded done, but no direct human approval event for the specification is evidenced in the permitted artifacts. Stage completion is not approval. Leave the input unchanged; do not claim approval or a fresh specify pass.

## Out of Scope / Gate

This plan is a planning artifact only; the human retains authority over any plan gate. It does not create implementation tasks or edit governance guidance/the diagram register template during this plan stage; the later documentation implementation is expected to update the template as specified above. No feature 033 or shared diagram is changed, and no application tests are run. The human retains plan-gate authority.

## Complexity Tracking

No constitution violations or exceptions.
