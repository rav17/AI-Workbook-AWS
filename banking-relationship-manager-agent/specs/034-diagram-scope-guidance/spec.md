# Feature Specification: Two-Level Diagram Scope Guidance

**Feature Branch**: `034-diagram-scope-guidance`

**Created**: 2026-11-12

**Status**: Draft

**Input**: Clarify the recommended two-level approach for draw.io diagrams: retain a solution-wide architecture baseline in `docs/architecture/`; keep full-lifecycle diagrams feature-local; link feature views to relevant baseline views; and make changes to shared architecture explicit and reviewed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep feature views local and baseline distinct (Priority: P1)

A feature author preparing architecture views for a full-lifecycle feature needs to describe feature-specific scope without replacing or duplicating the solution-wide architecture reference. The author keeps applicable feature views in the feature directory and treats existing solution-wide views as the baseline.

**Why this priority**: Clear ownership and separation prevent feature-specific views from silently becoming a competing shared architecture source.

**Independent Test**: Review the documented guidance and a representative feature diagram register. Confirm it places feature views under the feature directory, preserves the shared baseline location, and does not require every candidate view to be created.

**Acceptance Scenarios**:

1. **Given** a feature on the full-lifecycle route with useful architecture views, **When** the author records those views, **Then** they remain feature-local and do not become copies replacing the shared baseline.
2. **Given** an ideation discussion where a sketch may help, **When** the guidance describes the sketch, **Then** it is explicitly conceptual and optional, not an approved design or mandatory deliverable.

### User Story 2 - Relate a feature view to relevant baseline views (Priority: P1)

A feature author or reviewer needs to understand which solution-wide views inform a feature view, what the feature view adds, and whether a shared view is relevant at all.

**Why this priority**: Traceable links let readers compare the feature-specific scope with the established architecture without duplicating baseline content.

**Independent Test**: Inspect guidance for applicable, not-applicable, and missing/stale/conflicting baseline cases. A reviewer can follow relative links and find a short relevance description and the feature-specific scope or difference.

**Acceptance Scenarios**:

1. **Given** a relevant shared baseline view, **When** an applicable feature view is registered, **Then** its index entry provides a navigable relative link and a short description of relevance and feature-specific scope or differences.
2. **Given** no baseline view is relevant, **When** the feature author registers a view, **Then** guidance does not require a fabricated link or an irrelevant baseline reference.
3. **Given** a baseline is missing, stale, or conflicts with confirmed feature scope, **When** the discrepancy is found, **Then** the gap or conflict and relevant source artifacts are recorded and revalidation is requested from the designated architecture owner; neither the feature view nor the baseline is presumed correct or aligned.

### User Story 3 - Review proposed changes to shared architecture (Priority: P2)

A feature author or architecture reviewer needs shared-view changes to be visible as cross-feature changes, with enough context to assess impact before a shared view is changed.

**Why this priority**: Shared diagrams may inform multiple features; explicit review prevents an unexamined feature change from altering the solution-wide reference.

**Independent Test**: Review the guidance against a sample shared-view change proposal. Confirm it names the baseline view, explains the rationale and affected feature views or features, and records the review outcome before the shared view is changed.

**Acceptance Scenarios**:

1. **Given** a feature change may require an update to a shared diagram, **When** the change is proposed, **Then** the proposal identifies the affected baseline view, rationale, expected impact on other features, and the designated architecture owner's recorded review outcome; the shared view is changed only after explicit approval.
2. **Given** the designated architecture owner's outcome is pending, rejected, or conditional, **When** a shared-view change is considered, **Then** the change is not applied; a conditional outcome permits no change until its conditions are addressed and the owner records explicit approval.
3. **Given** a shared diagram has passed structural validation, **When** a reviewer assesses it, **Then** structural validation is not treated as proof of architectural correctness, completeness, or approval.

### Edge Cases

- A baseline view is absent, stale, or inconsistent with confirmed feature scope: record the specific gap/conflict and relevant sources, request revalidation from the designated architecture owner, and do not invent facts or silently reconcile the views. A baseline is stale when a relevant source artifact has been superseded or changed since that baseline's last recorded review; if that review point or source status cannot be established, record the uncertainty and request revalidation rather than claiming the baseline is current.
- A feature has no relevant baseline view: do not require a link; state non-applicability only where it helps the reader understand the omission.
- A shared change could affect features beyond the requesting feature: identify those impacts for review; do not assume the initiating feature is the only consumer. Pending, rejected, and conditional outcomes block application; after conditional requirements are addressed, explicit approval from the designated architecture owner must be recorded before application.
- A diagram validator passes but reviewers have not assessed its content: report only the structural result, not architecture approval.
- Documentation examples or diagrams might expose sensitive information: use synthetic data and keep secrets and customer data out of documentation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Guidance MUST distinguish the solution-wide architecture baseline in `docs/architecture/` from feature-specific architecture views.
- **FR-002**: For full-lifecycle work, guidance MUST place useful feature-specific draw.io views and their register in `<feature-dir>/architecture/diagrams/`; it MUST NOT require every candidate view or duplicate the shared baseline as a feature deliverable.
- **FR-003**: Guidance MUST describe ideation sketches, when useful, as optional conceptual discussion artifacts and not as approved architecture.
- **FR-004**: The feature diagram register MUST identify applicability, status, source artifacts, and rationale when deferred or not applicable for each view, using navigable relative links.
- **FR-005**: When a relevant shared baseline view exists, the applicable feature-view entry MUST link to it and briefly state its relevance and the feature-specific scope or differences. Guidance MUST NOT require links to irrelevant views.
- **FR-006**: Guidance MUST require each baseline review record to identify the reviewed baseline view, review point, and relevant source artifacts. The minimum review-point record MUST include a timezone-aware date and time, the reviewer's identity and role (including whether the reviewer is the designated architecture owner), and, for each relevant source artifact, its identifier and version or revision. If a source version/revision or status cannot be established, the record MUST identify that uncertainty and request revalidation rather than imply verification. A relevant baseline is stale when a relevant source artifact has been superseded or changed since that recorded review. When a relevant baseline is missing, stale, or conflicts with confirmed feature scope, guidance MUST require recording the gap or conflict and relevant source artifacts and requesting revalidation from the designated architecture owner. For a missing baseline, the owner review MUST determine whether a shared baseline is relevant and what follow-up is appropriate; guidance MUST NOT require a fabricated link. If the last review point or source status cannot be established, guidance MUST require recording that uncertainty and requesting revalidation. Guidance MUST NOT presume the baseline or feature view is correct or aligned, or present an unverified diagram as authoritative.
- **FR-007**: Before a shared baseline view is changed, the proposal MUST identify the affected view, rationale, and expected impact on other feature views or features, and MUST record the outcome of review by the designated architecture owner. Only explicit owner approval permits application. Pending, rejected, or conditional outcomes MUST block application; after conditions are addressed, the owner MUST record explicit approval before application. A change without that recorded approval MUST NOT be represented as reviewed or ready to apply.
- **FR-008**: Guidance MUST distinguish structural diagram validation from architecture review: a structural pass checks format/references only and MUST NOT be described as proof of factual correctness, completeness, security, or approval.
- **FR-009**: Documentation and diagram examples MUST use synthetic data where data is needed and MUST NOT include customer data or secrets.
- **FR-010**: This feature MUST permit changes to diagram-governance guidance needed to establish the requirements above. In this refactor, it MUST NOT edit or change any existing solution-wide architecture diagram files in `docs/architecture/`.

### Key Entities

- **Shared baseline view**: A solution-wide architecture diagram maintained in `docs/architecture/` and potentially relevant to multiple features.
- **Feature view**: A feature-scoped draw.io diagram under the feature architecture diagrams directory that records confirmed feature-specific scope.
- **Diagram register entry**: A feature-local record of applicability, status, sources, rationale, and relevant baseline link when one exists.
- **Shared-view change review**: A recorded review by the designated architecture owner of a proposed shared baseline change, including the affected view, rationale, cross-feature impact, outcome, and any conditions and their disposition. Only an explicit recorded approval authorizes application.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of applicable full-lifecycle diagram-register entries with a relevant shared baseline, reviewers can navigate from the feature entry to that baseline view and identify the stated relevance and feature-specific difference or scope.
- **SC-002**: 100% of shared-view changes applied identify the affected baseline view, rationale, expected cross-feature impact, and explicit approval recorded by the designated architecture owner before application. For 100% of applied changes with a conditional review outcome, every condition is recorded as satisfied before the owner records subsequent explicit approval, and that approval precedes application. Zero changes are applied while review is pending or rejected, or while any condition remains unmet; a conditional outcome alone is never treated as approval.
- **SC-003**: Reviewers can distinguish structural validation results from architecture approval in every documented validation instruction; no structural pass alone is presented as architectural approval.
- **SC-004**: In 100% of cases where the last review point or relevant source identity, version/revision, or status cannot be established, the record identifies each unknown as uncertain and requests revalidation from the designated architecture owner; no unknown is represented as verified. Missing, stale, or conflicting baselines are likewise recorded with relevant sources and a revalidation request, without a fabricated link or unverified alignment claim.
- **SC-005**: 100% of the pre-existing `docs/architecture/*.drawio` files remain byte-for-byte unchanged during this refactor; zero pre-existing shared diagram files are added, deleted, or modified.

## Assumptions

- `docs/architecture/` is the intended solution-wide baseline location, as requested and evidenced by existing solution-wide draw.io views there.
- Full-lifecycle diagrams remain feature-local; this does not impose diagrams on refactor or other routes that do not invoke the full-lifecycle diagram workflow.
- Not every feature view has a relevant shared baseline view, and not every candidate diagram type is useful for every feature.
- Existing repository diagrams are evidence of the current baseline location and view inventory, not by themselves proof that every view is current, factually correct, or formally approved.
- The designated architecture owner is the authority for approving shared baseline changes. If no owner is designated or available, shared changes remain blocked until one is designated and provides an explicit recorded approval.
- The change described by this feature is governance guidance. Existing solution-wide diagram files are not changed in this refactor; updating the guidance itself is in scope.
- Existing documentation-safety knowledge applies: use synthetic data where needed and do not put customer data or secrets in specifications or diagram documentation. This feature adds no customer-decision audit obligation.

## Repository Evidence

- `docs/architecture/` contains solution-wide draw.io views including `01_System_Context_Diagram.drawio`, `02_Architecture_Overview.drawio`, `03_Component_Model.drawio`, `01_Key_NFRs.drawio`, and `07_Security_Viewpoint.drawio`.
- `docs/speckit-profiles.md` (Profiles) describes full-lifecycle diagrams as applicable, feature-local views under `<feature-dir>/architecture/diagrams/`, an `index.md` with applicability and source references, and a validator that checks XML and graph references rather than architecture correctness.
- `.github/skills/speckit-diagrams/SKILL.md` (Location and register; Lifecycle mapping; validation guidance) says diagrams are feature artifacts, only useful views should be created, relative links are used, and the index tracks applicability/status/sources. It says ideation sketches are optional and conceptual, while specify creates a context view from confirmed scope. Its validator does not establish factual correctness, completeness, security, or approval.
- `docs/speckit-portability.md` (full-lifecycle portability notes) likewise limits validator claims to XML and graph references, not service icon identity or architectural correctness.
- `.specify/knowledge/banking-compliance.md` says customer data must not appear in specs or tests and synthetic data should be used; it also requires secrets to stay out of source control. No additional regulatory obligation is inferred for this documentation-governance feature.
