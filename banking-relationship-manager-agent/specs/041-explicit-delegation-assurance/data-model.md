# Data Model: Explicit Delegation Assurance

## Acceptance event

Use the existing audit envelope with new type `delegation_assurance_accepted`.
Its stage identifies the accepted current stage; actor must be a non-empty
`human:` identity. No lifecycle state or gate is changed.

The bounded detail contains a version, host label, session identifier, grouped
SHA-256 scope fingerprint, nonempty short rationale, sanitized observation,
and explicit missing-evidence/residual-risk text as disclosed to the human.
Use bounded host/session identifiers (24/64 characters) and short rationale and
observation (60 characters each). Serialize compactly and enforce the existing
500-character event limit and redaction before any write; individual field
limits do not waive the aggregate limit.
Host/session labels must be bounded non-sensitive identifiers, not paths or
arbitrary log contents. Retain the existing redaction checks.

The scope fingerprint covers:

- Resolved feature location, stage and effective profile/assignments.
- Selected named workers plus the conductor and their full current definitions.
- Host/session context.
- Latest relevant stage redo or call-budget reset boundary.

The normal start of a previously pending stage does not invalidate acceptance.
A redo/reset does. A different feature, stage, configuration, host or session
does not reuse it. Audit/parse errors fail explicitly; do not silently select
an older event after a malformed or mismatched newer decision.

## Read-only status

Statuses distinguish absent acceptance, stale/context-mismatched acceptance,
ineligible work and `unverified_accepted`. Every status retains
`runtime_enforcement: unverified` and an explanatory reason.

Dispatch inspection may show that an acceptance was recorded, but without an
explicit current host/session it reports context checking required. Only the
context-bound status check can recognize current acceptance.

No status returned here means verified isolation, gate approval, safe worker
exclusion, completed tests, permission to access logs or permission to deploy.
