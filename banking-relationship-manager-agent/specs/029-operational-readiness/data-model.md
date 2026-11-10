# Data Model

## Release record (`release.md`)
Required level-two sections: Ownership and target, Configuration, Verification,
Rollout, Rollback. Each section contains substantive content and
`- Evidence: <human-supplied reference or reasoned non-applicability>`.

## Runbook (`runbook.md`)
Required level-two sections: Ownership, Health signals, Alerts, Incidents,
Rollback, Feedback. Same evidence requirement.

## Readiness sensor
Builtin `readiness`, no options, required for deploy/operate and scoped to
`release-ready`. Result uses existing status/timestamp/reason/fingerprints.
Fingerprint keys: spec.md, plan.md, tasks.md when present; both fixed readiness
records are included when validly readable. Missing records fail validation;
deletion changes the fingerprint set and invalidates earlier passes.

Limits: 256 KiB per record; UTF-8, regular non-symlink/reparse-point files only.
Placeholder-only/unchecked documents fail. No dependency or approval state is
created by checking; normal human gates remain authoritative.
