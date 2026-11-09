# Data Model

## Recommendation (transient)

- `profile`: available profile id, or null when clarification is needed.
- `candidates`: available candidate ids.
- `reason`: concise explanation; never contains the original request.
- `needs_clarification`: whether the user must select/classify the work.
- `confirmation_required`: always true for a new selection.
- `stages`, `gates`: resolved profile route, empty for an ambiguous recommendation.

Explicit profile selection validates the effective project/plugin profile set.
No recommendation creates feature state.

## Dispatch brief (transient)

- Feature, profile, stage, lead and ordered domain supports/independent reviewers.
- Agents include host name, definition path and edit permission.
- Assigned lead must be a domain agent and callable by conductor.
- Stage must be the current pending/in-progress routed stage with no pending gate.
- Complete features return `status=complete`, no dispatch.
- Broken audits, parked work, out-of-order stages or invalid agent settings fail.

The CLI returns `status=ready` only for eligibility, never as proof of invocation.
Actual dispatch remains a host operation. The delegated-stage marker is scoped
to the conductor brief and the matching stage; it grants no CLI permissions.

## Persisted state

Reuse `state.json`, rendered `state.md`, `audit.jsonl`, existing profiles and
reviews/sensors. No new mutation mechanism or actor authorization is introduced.
