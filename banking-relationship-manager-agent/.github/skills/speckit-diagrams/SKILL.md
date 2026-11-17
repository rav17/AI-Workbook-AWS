---
name: speckit-diagrams
description: "Create, update, and review feature architecture diagrams in editable draw.io format across the Spec Kit full-lifecycle stages."
---

# Spec Kit Architecture Diagrams

Use this skill's feature-diagram workflow only for a feature on the `full-lifecycle`
route when architecture views are useful. Diagrams are feature artifacts, not
copies of the solution-wide baseline. Keep the shared architecture baseline in
`docs/architecture/`; feature-specific views belong only in that feature's
`architecture/diagrams/`. Do not copy baseline diagrams into a feature directory.
This skill does not impose diagrams on non-applicable routes, including refactor.
Use only facts in the feature artifacts, repository evidence, or explicit
stakeholder answers. Mark unresolved details as unknown; never invent
components, integrations, cloud services, data flows, or deployment topology.

## Location and register

Keep diagrams in the feature directory:

```text
<feature-dir>/
└── architecture/
    └── diagrams/
        ├── index.md
        ├── context.drawio
        ├── overview.drawio
        ├── components.drawio
        ├── interactions.drawio
        ├── deployment.drawio
        └── operations.drawio
```

Create only views that are useful for this feature. Maintain `index.md` from
`./assets/index-template.md`; record each view's applicability, status, source
artifacts, and rationale when deferred or not applicable. Use relative links.
Do not create empty or speculative diagrams just to fill the list.

An ideation sketch may be made only when useful for discussion; it is optional,
conceptual, and not an approved design. Candidate view types are not a required
set: create only useful views, and do not create empty or speculative diagrams.

Use uncompressed, editable draw.io XML (`mxfile` with `mxGraphModel`) so changes
are reviewable in source control and open in diagrams.net or the draw.io VS Code
extension. Give diagrams a clear title, legible labels, and directional arrows
for flows.

## Baseline traceability and review

In the feature register, use a navigable relative link only for a relevant
solution-wide baseline view, and state why it is relevant and the feature-specific
scope or differences. A view with no relevant baseline does not need a link.
Never fabricate a baseline path, presume views are aligned, or present an
unverified view as authoritative.

For each baseline review, record its identifier/path (or explicitly missing
status), a timezone-aware review date and time, reviewer identity and role,
whether the reviewer is the designated architecture owner, and each relevant
source artifact identifier with its version or revision. If the review point or
source version/status cannot be established, mark that evidence explicitly as
uncertain and request designated-owner revalidation; do not imply it was verified
or that the baseline is current. A relevant baseline is stale when a relevant
source artifact has been superseded or changed since the recorded review.

Record missing, stale, or conflicting baseline gaps and their relevant source
artifacts, and request review/revalidation from the designated architecture
owner. For a missing baseline, that owner must determine and record whether a
shared baseline is relevant, what follow-up is appropriate, and the rationale.
Until the owner records this disposition, it is pending: assert neither relevance
nor a baseline link. Do not fabricate a path; after a relevant disposition, link
only to a verified existing baseline view.

## Technology icons

When a diagram names a specific cloud provider service, use that provider's
matching service icon from draw.io's built-in shape libraries. Examples include
`mxgraph.aws4` for AWS, `mxgraph.azure2` for Azure, and `mxgraph.gcp3` for Google
Cloud; use the current draw.io library's exact shape identifier for the selected
service (for example, AWS resource icons use `shape=mxgraph.aws4.resourceIcon`
with the matching `resIcon`). Search the shapes library for the exact service
name before using an icon. Do not guess icon identifiers or substitute an icon
for a different service.

Use the icon together with a readable service name (for example, "Amazon S3"),
not as a replacement for the label. For a hybrid or multi-cloud design, use the
correct icon set for each provider and keep provider boundaries clear. Use
neutral shapes for project-owned components, generic infrastructure, or
services whose implementation has not been selected; never imply a provider or
service choice that the source artifacts do not confirm.

Prefer native draw.io stencils or embedded icon data so diagrams remain
editable and do not depend on remote image URLs at render time. If the precise
service icon is unavailable, keep a clearly labeled neutral shape and record
the missing icon in the diagram register rather than using a misleading icon.
When changing an existing diagram, preserve its visual conventions unless
they conflict with service accuracy or readability.

## Lifecycle mapping

| Stage | Diagram action |
|---|---|
| Ideation | Optionally sketch a clearly marked concept when it improves discussion; it is not an approved design. |
| Specify | Create or update `context.drawio` from confirmed actors, system boundaries, and external systems. |
| Clarify | Update affected views only from answers; list unanswered architecture questions in the feature's questions mechanism. |
| Plan | Create or refine `overview.drawio`, `components.drawio`, and `interactions.drawio` when supported by the spec and decisions. |
| Tasks | Add explicit tasks to create, verify, or update each applicable diagram; reference its path and acceptance criteria. |
| Analyze | Check every view against the spec, plan, decisions, and other views. Return contradictions and unsupported assumptions as findings; do not silently rewrite the artifact under review. |
| Implement | Update only views affected by implemented design changes and keep decisions traceable. |
| Deploy | Create or refine `deployment.drawio` from the approved deployment plan, environments, and release artifacts. |
| Operate | Create or refine `operations.drawio` for confirmed health signals, monitoring, support, recovery, and operational feedback. |

These are candidate views, not mandatory deliverables. A context or overview
diagram may be enough for a small feature. A sequence diagram is useful only
when a non-trivial interaction needs explanation. The operational view extends
the deployment view; keep them separate only when that improves clarity.
Represent an agile initial architecture by evolving the overview rather than
creating a second copy. The course's architectural-thinking-process diagram is
reference material, not a project architecture deliverable.

## Shared baseline changes

Before changing a shared baseline view, record the affected view, rationale,
expected impact on other feature views/features, designated architecture owner
identity and role, and the owner's outcome in
`./assets/shared-change-proposal-template.md`. Pending and rejected outcomes
block application. A conditional outcome also blocks application, even after
work on its conditions is proposed; record evidence that every condition is
satisfied, then obtain and record the designated owner's subsequent explicit
approval before applying the change. No owner, decision, or approval is inferred.

A successful XML/graph structural validation checks format and graph references
only. It does not establish architectural correctness, completeness, security,
or approval, and can never authorize a shared-view change. When examples are
needed, use synthetic information only; never include customer data or secrets.

## Create or update

1. Read the current stage's source artifacts and the existing diagram register.
2. Decide which views are applicable now. Distinguish confirmed facts,
   decisions, and unknowns in labels or notes.
3. Identify the specific technologies named in the source artifacts. For each
   named provider service, search the draw.io shape library and select its exact
   provider/service icon. Do not infer the technology from project context.
4. Generate or edit the corresponding draw.io XML. Preserve stable element IDs
   where practical so later diffs remain understandable.
5. Update `index.md` with relative paths, status, stage, exact source artifacts,
   and any unavailable provider icons. Mark a diagram draft until reviewed; do
   not imply approval.
6. Run `python -m speckit_flow diagrams validate --feature-dir <feature-dir>`.
   Fix all validation failures before reporting the stage result.
7. Report generated or changed paths, deferred views and reasons, technologies
   represented by provider-specific icons, any unavailable icons, unknowns,
   and validator output to the conductor.

Validation checks XML structure and graph references only. It does not prove
that a diagram is factually correct, complete, secure, or approved; stage
reviewers must compare it with its sources.
