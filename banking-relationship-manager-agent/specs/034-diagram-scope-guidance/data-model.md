# Data Model: Diagram Governance Concepts

**Feature**: `034-diagram-scope-guidance`

This is a conceptual vocabulary for documentation records required by the specification. It is not an application data model, persistence schema, customer/transaction record, or proposed API.

## Entities

### Solution-wide baseline view

A solution-scoped architecture diagram maintained under `docs/architecture/` and potentially relevant to multiple features.

- **Identifier**: repository-relative path/name (or an explicit `missing` status; never a fabricated path).
- **Review status**: established only by a recorded review; file presence alone does not establish approval or freshness.
- **Relevant sources**: source artifact identifiers with versions/revisions and status when established.
- **Relationship**: may be referenced by a feature-view register entry or a shared-view change proposal. The future register template provides a baseline link/relevance field and the FR-006 review-evidence field set.

### Feature view

A useful feature-specific diagram stored under that feature's `architecture/diagrams/` on the full-lifecycle route.

- **Identifier/link**: feature-relative path, if a diagram exists.
- **Sources**: relevant spec sections, decisions and other source artifacts.
- **Scope/difference**: short statement of what feature-specific information it adds relative to a relevant shared baseline.
- **Relationship**: may point by navigable relative link to zero or more relevant baseline views. For a missing baseline, no link is asserted until the designated architecture owner reviews the gap and determines whether a shared baseline is relevant; no fabricated link is required. If the owner determines none is relevant, absence of a link is valid.

### Diagram register entry

A feature-local record that makes each candidate view's applicability and provenance legible.

- View kind, status, relative diagram link or explicit absence.
- Source artifact identifiers/links.
- Applicability and rationale, including why deferred or not applicable.
- Relevant baseline link(s), relevance, and feature scope/difference when applicable.
- Uncertainty/gap/conflict and owner-revalidation request where baseline status cannot be established.

### Baseline review record

An auditable point-in-time record for a relevant shared baseline view.

- Baseline view identifier and timezone-aware review date/time.
- Reviewer identity and role, including whether the reviewer is the designated architecture owner.
- Each relevant source artifact's identifier and version/revision.
- Unknown source version/status recorded explicitly as uncertain with revalidation requested.
- Missing, stale or conflicting baseline gap and related sources, with a request for designated-owner review/revalidation. For a missing baseline, the designated architecture owner reviews the gap, determines whether a shared baseline is relevant, and records the appropriate follow-up and rationale. Until that relevance determination is recorded, no baseline link or relevance is asserted; no fabricated link is required.

The future `index-template.md` review field set is: baseline view identifier or explicit missing status; timezone-aware reviewed-at date/time; reviewer identity and role; designated-owner yes/no status; relevant source identifiers and versions/revisions; explicit uncertainty for unknown source version/status; and gap/conflict with owner revalidation request; for a missing baseline, owner disposition (pending / relevant / not relevant), appropriate follow-up, and rationale. While pending, assert neither relevance nor a link. These are documentation fields, not application persistence.

A baseline is stale when a relevant source has been superseded or changed since the recorded review. If the review point or source status cannot be established, the record must not imply currency.

### Shared-view change proposal and outcome

A governance record used before changing a shared baseline.

- Affected baseline view, rationale, and expected impact on other features/views.
- Designated architecture owner's identity/role and recorded outcome.
- Outcome status: pending, rejected, conditional, or explicitly approved.
- For a conditional outcome: conditions, evidence of satisfaction, and subsequent explicit owner approval before any application.

The future `shared-change-proposal-template.md` field set is: affected baseline view; rationale; expected impact on other features/views; designated owner identity/role; outcome (pending, rejected, conditional, explicitly approved); conditions; evidence each condition is satisfied; and subsequent explicit owner approval. The skill procedure must prohibit application until that explicit approval is recorded after condition satisfaction.

**Transition/validation rule**: Pending and rejected block application. Conditional also blocks application, including after proposed work on the conditions, until the owner records that all conditions are satisfied and then records explicit approval. Only that explicit approval permits application. A structural validator result does not change this state.

## Relationships and non-persistence

A register entry may link a feature view to an applicable baseline; a review record supports baseline-status claims; a change proposal references the affected baseline and its cross-feature impacts. These are documentation concepts only. No storage engine, retention period, typed runtime model, customer data, or transactional audit event is introduced.
