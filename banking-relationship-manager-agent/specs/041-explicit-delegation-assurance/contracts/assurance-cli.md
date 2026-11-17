# Proposed CLI Contract

All commands use the receiving project root and an explicit feature directory.
The following interface is proposed, not implemented yet.

## Human acceptance

```text
python -m speckit_flow workflow assurance accept
  --feature-dir <feature> --stage <stage> --host <host-label>
  --session-id <current-session> --reason <bounded-rationale>
  --observation <sanitized-current-observation>
  --confirm-ordinary-work --actor human:<operator>
```

Required: actual human decision following the complete review package. The
confirmation states that the scoped work is ordinary and does not require
verified isolation; it does not turn an unsafe task into ordinary work.
Agents cannot run this operation through the guard. Reject nonhuman actors,
bad identifiers, ineligible profiles/stages and invalid lifecycle/audit state.
Validate the complete detail/redaction before appending the acceptance event.
Return success indicating recorded acceptance, not host certification.

The audit detail retains the disclosed observation, missing evidence and residual
risk as text, alongside scope/context and rationale. Host/session labels are
bounded to 24/64 characters, rationale/observation to 60 each, and the complete
serialized detail to the existing 500-character limit. Existing redaction
rejects sensitive detail; do not truncate or silently drop disclosure fields.

This is the existing human-terminal operational decision process, not human
authentication. The human personally runs the command; an actor label alone
cannot establish that fact. The guard blocks agent-tool acceptance even with a
human-shaped actor, but is not a sandbox against arbitrary/compromised local
processes. Such threats cannot be made eligible by this exception.

Host/session identifiers must be the current ones explicitly supplied by host
metadata, whose source is disclosed in the acceptance package. Comparing labels
checks the attested scope; it cannot independently authenticate the host or
detect a context change concealed by a caller. Unknown context remains a stop.

## Context-bound inspection

```text
python -m speckit_flow workflow assurance status
  --feature-dir <feature> --stage <stage> --host <host-label>
  --session-id <current-session> --json
```

Return structured status/reason, feature/stage/context, assigned workers,
declared restrictions, missing runtime evidence and the acceptance event
reference when current. Keep human-facing text equally explicit.

Exit 0 only for current `unverified_accepted`; use exit 1 for absent, stale or
ineligible acceptance and standard explicit errors for malformed inputs/audit.
This exit code answers acceptance validity only: independent dispatch/recovery,
failure, gate and review checks remain mandatory before invocation.

## Existing workflow inspection

Dispatch/next retain eligibility semantics and add a non-authorizing assurance
summary. No supplied current context means a stored acceptance cannot be
presented as currently validated. Existing human-gate, strict hybrid-review and
call-accounting errors take precedence over any acceptance.
