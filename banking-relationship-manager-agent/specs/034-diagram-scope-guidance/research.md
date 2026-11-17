# Research: Two-Level Diagram Scope Guidance

**Feature**: `034-diagram-scope-guidance`  
**Date**: 2026-11-13

Research resolves the design questions for the documentation-only refactor using the current draft-status specification as its input. The specify stage is recorded done, but the permitted evidence does not establish a direct human approval event for the specification; stage completion is not specification approval. The spec was not edited, and no approval or fresh specify pass is claimed.

## Verified Repository Evidence

| Source | Current evidence and scope |
|---|---|
| `specs/034-diagram-scope-guidance/spec.md` | FR-001 through FR-010 and SC-001 through SC-005 define baseline/feature separation, register links, auditable review records, explicit architecture-owner approval, validator limits, synthetic examples, and byte-for-byte baseline preservation. The two-level approach is the requirement stated by the current draft-status specification. |
| `.github/skills/speckit-diagrams/SKILL.md` (Location and register; Lifecycle mapping; Create or update) | Applies on `full-lifecycle`; keeps useful diagrams feature-local; uses a relative-link `index.md` with applicability/status/sources/rationale; treats ideation sketches as optional concepts; says validator checks XML/graph references only, not correctness, completeness, security or approval. |
| `.github/skills/speckit-diagrams/assets/index-template.md` | Current register fields include view, status, diagram, source artifacts, applicability/rationale and provider-icon check. It contains no prescribed shared-baseline-link field. The plan therefore commits this template as an implementation surface: add an explicit shared-baseline relative-link field and a relevance / feature-specific-scope-or-differences field. The plan correction also assigns this template the FR-006 baseline-review field set, assigns procedure and owner-disposition requirements to `SKILL.md`, and requires a new `assets/shared-change-proposal-template.md` for FR-007/FR-008 outcome sequencing. |
| `docs/speckit-profiles.md` (Profiles) | Confirms full-lifecycle uses feature-local diagrams and a register; validator scope is structural. Its profile table lists `refactor` as specify -> plan -> tasks -> implement, minimal depth, plan gate; it is not the full-lifecycle route. |
| `docs/speckit-portability.md` (full-lifecycle diagram notes) | Repeats that structural validation does not establish icon identity or architectural correctness. No additional behavior is inferred. |
| `docs/architecture/` | Current listing contains exactly 14 `.drawio` files: `01_Key_NFRs`, `01_System_Context_Diagram`, `01_Use_Case_Diagram`, `02_Architecture_Overview`, `03_Component_Model`, `03_Sequence_Chat_Message`, `03_Sequence_Proactive_Event`, `04_Deployment_Unit_Model`, `04_Location_Model`, `05_LOM`, `05_POM`, `07_Architecture_On_A_Page`, `07_Security_Viewpoint`, `08_Aria_End_State_Architecture`. This confirms location and inventory only; it does not prove correctness, freshness or approval. |
| `specs/004-receivables-exception-resolution/architecture/diagrams/index.md` | A current example of a feature-local register with relative links to its feature artifacts and explicit applicability/deferred statuses. It does not establish whether a shared baseline link is relevant; no migration or change to feature 004 is in scope. |
| `.specify/memory/constitution.md` | No implementation/security/state principle is changed by this documentation-only feature. Documentation of architecture decisions and safe handling remain applicable. |
| `.specify/knowledge/banking-compliance.md` | Requires synthetic data and no customer data in specs/tests; secrets stay out of source control. No further regulatory obligation is inferred. |

A repository search identified the active diagram skill, its register template and the profile/portability docs as direct guidance references. Generated `graphify-out` matches are indexes/reports, not authoritative architecture guidance and are not proposed for change.

No feature-local `codebase.md` exists, so there is no prior codebase-analysis evidence to consume or validate. The current skill, template, profile/portability docs and one existing feature register were inspected directly. No codebase inventory establishes the application architecture or successful tests; this is a documentation-only plan and makes no such claims. Coverage is limited to these relevant guidance artifacts and a filename inventory of shared diagrams. The inventory does not validate diagram content, currentness, owner approval, or every feature-to-baseline relationship.

## Decisions

### D1. Required FR-005 and FR-006 register-template fields

**Decision**: The future implementation MUST update `.github/skills/speckit-diagrams/assets/index-template.md` with FR-005's dedicated shared-baseline relative-link and relevance / feature-specific-scope-or-differences fields, and FR-006's baseline review record fields: baseline view identifier or explicit missing status; timezone-aware review date/time; reviewer identity and role; designated-architecture-owner status; each relevant source artifact identifier and version/revision; explicit uncertain source version/status; and gap/conflict plus owner revalidation request. For a missing baseline, include owner disposition (pending / relevant / not relevant), appropriate follow-up, and rationale; while pending, assert neither relevance nor a link. `.github/skills/speckit-diagrams/SKILL.md` MUST instruct authors how to record missing/stale/conflicting baselines and require the designated architecture owner to determine and record missing-baseline relevance, appropriate follow-up, and rationale. Until that missing-baseline disposition is recorded, neither relevance nor a link may be asserted. Do not edit any draw.io file or feature 004's existing register.

**Rationale**: A template field set makes review evidence reusable and auditable, while skill procedure defines the owner decision that cannot be inferred from a missing file or register omission. FR-010/SC-005 freeze existing solution-wide diagrams.

**Alternatives rejected**: Leaving FR-006 alignment to optional wording; treating a directory listing or validator as a review; asserting relevance/link before owner determination; updating shared diagrams; copying baseline views; retrofitting feature 004, which expands scope and assumes relevance not established here.

### D2. Required FR-007/FR-008 shared-change proposal surface and sequence

**Decision**: The future implementation MUST add `.github/skills/speckit-diagrams/assets/shared-change-proposal-template.md` and specify its required fields: affected baseline view; rationale; expected impact on other feature views/features; designated owner identity and role; outcome (pending, rejected, conditional, or explicitly approved); conditional requirements; evidence that all requirements are satisfied; and a subsequent explicit owner approval record. `SKILL.md` MUST make pending, rejected, and conditional outcomes blocking; recorded satisfaction of conditions is not approval; explicit owner approval after satisfaction and before application is required. Structural validation remains separate and cannot authorize application.

**Rationale**: A named reusable proposal artifact prevents FR-007/FR-008 sequencing and evidence from being left to later discretion and makes the gate inspectable.

**Alternatives rejected**: Treating general prose as sufficient without a proposal field set; treating conditional status or completion of conditions as approval; treating structural validation or informal consensus as authorization.

### D3. Route-specific diagrams are not applicable

**Decision**: Create no feature-local draw.io views or `architecture/diagrams/index.md` for feature 034. Guidance should describe the feature-local convention for applicable full-lifecycle features, while this refactor itself remains diagram-free.

**Rationale**: `refactor` does not invoke the full-lifecycle diagram workflow, and this feature introduces guidance rather than a runtime architecture.

**Alternatives rejected**: Creating overview/component/interaction diagrams solely because they are candidate types; linking this feature to an arbitrary shared view without a feature architecture that needs it.

### D4. Owner decisions are recorded separately from structure checks

**Decision**: Guidance must define explicit outcomes and the block/approval sequence from FR-006 through FR-008. A missing owner or uncertain/stale source blocks applying a shared change pending owner designation/revalidation; a conditional outcome requires recorded satisfaction of all conditions and later explicit approval. XML/graph validation is only structural evidence.

**Rationale**: This preserves a human-controlled architecture decision and avoids equating a machine check with authority.

**Alternatives rejected**: Treating a conditional outcome, silence, reviewer role, or structural pass as permission; inferring an owner identity from repository contents.

### D5. Baseline boundary and evidence method

**Decision**: Keep all 14 baseline paths and bytes unchanged. In later implementation, capture and compare a pre-change and post-change path inventory and SHA-256 hashes; test additions/deletions as well as modifications.

**Rationale**: A `git diff` check alone may not detect untracked files; path-set and hash comparison directly evidence SC-005.

**Alternatives rejected**: Relying on visual review, a diagram validator, or a diff of tracked modifications alone.

### D6. No runtime data model or interface contract

**Decision**: Describe register/review/proposal records as conceptual governance entities only; do not design application persistence or a public API/CLI contract.

**Rationale**: No code, state transition in the agent product, or external interface is introduced.

**Alternatives rejected**: Inventing Pydantic fields, a database schema, API or command surface not required by the current specification.

## Domain-Support Contributions

- **aws-platform**: No AWS/infrastructure/deployment/data/model contract applies. Do not infer cloud services from the wider project; baseline existence is not approval/correctness evidence.
- **devsecops**: Preserve all 14 baseline files; keep scope to governance guidance, use feature-local links without copies, make stale/uncertain cases explicit, and use before/after hashes. No approval is implied by validation.
- **compliance**: Documentation-only, no new regulatory/customer-data/retention impact. Use synthetic examples only. FR-006 is architecture-review traceability, not transaction audit. Pending/rejected/conditional outcomes block application.

These contributions are supporting scope checks, not independent review verdicts or approvals.

## Evidence Status Note

The saved `specify-3` review is stale for the current checklist. Historical `plan-1` and `plan-2` review artifacts are also stale; their saved verdicts are concerns, not current passes. Recorded concerns included making the register-template update an explicit implementation surface, removing historical invocation/review narrative, not asserting specification approval without provenance, and requiring the designated architecture owner to determine and record missing-baseline relevance and follow-up. These historical concerns are not represented as current review results or approvals. 

## Unknowns and Resolution

- **Named architecture-owner identity**: Intentionally not supplied or inferred. The specification designates the owner by role; do not infer a person or treat role designation as evidence an owner is currently assigned. The future guidance must preserve the stop condition for shared changes when approval is unavailable.
- **Whether a relevant baseline exists for a specific feature view**: Feature-dependent and not determined by the inventory. Where the baseline is missing, the designated architecture owner must review the gap and record whether a shared baseline is relevant and the appropriate follow-up, with rationale. Until then, assert neither relevance nor a link; do not fabricate one. For stale/conflicting/uncertain evidence, record the gap and request owner revalidation. No per-view link is invented in this plan.
- **Whether baseline diagrams are current/correct/approved**: Not established by an inventory. Record as unknown unless a review record and source revisions support it; guidance must not claim otherwise.
- **Data/API/cloud/implementation choices**: Not applicable; this feature creates no runtime surface. No further research uncertainty remains for this stage.
