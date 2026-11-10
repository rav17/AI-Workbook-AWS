# Research

## Existing stages, optional profile
- Decision: Reuse deploy/operate and existing pipeline-deploy/operations agents.
- Rationale: Core already models these stages and gates; new mandatory stages
  would add ceremony without solving an unmet lifecycle need.
- Rejected: Automatic production checks/deployment; not requested and unsafe.

## Dedicated structural sensor
- Decision: Add `readiness` builtin with fixed feature-local files and headings.
- Rationale: Existing `section` accepts arbitrary body text, including template
  instructions, and is restricted to spec/plan/tasks. Readiness needs evidence
  and stale-record protection without changing established section behavior.
- Rejected: Configurable schema engine or JSON approval records; unnecessary
  abstraction for two human-reviewable operational documents.

## Scoped fingerprints
- Decision: Add release/runbook hashes only for readiness results.
- Rationale: Global artifacts would invalidate unrelated sensors after runbook
  edits. Existing gate/audit mechanics can be reused without new state events.
- Limitation: Linked evidence truth and freshness are reviewed by humans.

## Portability
- Decision: Disabled plugin, explicit bundle allowlist, provider-neutral templates.
- Rationale: Source application policies/test commands must not reach targets.
- Rejected: Automatically enabling packs or auto-generating approval evidence.
