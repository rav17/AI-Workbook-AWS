# Clarifying Questions

## Q1 [role: product]
What host evidence and execution-exclusion boundary can be trusted to distinguish running, delayed, unavailable, and unknown from safely ceased, and what maximum wait/report bound should operators expect?

**Answer:** Use durable host-issued identity/fencing receipts; block unsupported hosts; propose 10-second total wait and 2-second adapter-call cap

## Q2 [role: product]
What exact evidence makes a saved checkpoint verified and resumable, and which changes (artifacts, dependencies, commands, or reviews) must invalidate it?

**Answer:** Require matching completion evidence, relevant inputs/dependencies/instructions and verification bindings; invalidate affected dependents; block ambiguous progress or side effects

## Q3 [role: product]
Which recovery actions, if any, may proceed under a human autonomy grant without per-action approval, how is the human's authorization provenance established, and how can that grant be bounded and revoked?

**Answer:** Deferred/out of scope for this feature; no autonomy grant is approved or implied.
