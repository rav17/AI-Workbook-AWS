# Research: Explicit Delegation Assurance

## Decision: Bounded opt-in, not blanket removal

The conductor currently stops when tool enforcement is unverified even though
ordinary dispatch can be ready. Keep that default, allowing a separately recorded
human decision only for ordinary work. Deleting the stop globally would silently
weaken strict and existing workflows; a diagnostics-only edit already proved
insufficient in feature 040.

## Decision: Existing audit, not a second approval database

Reuse `audit.append_event`, its 500-character detail limit, redaction and chain
inspection. Add one explicit acceptance event with a compact scope digest.
Include a bounded sanitized observation and the actual disclosed missing
evidence/residual-risk text, not just a digest of them. Store no raw prompt/tool
output or source-log path. Group digest hex digits, as
existing host evidence does, to avoid conflict with the secret-shaped-hex check.
A mutable acceptance file would add an unnecessary second binding/write failure.

## Decision: Declared scope and disclosed context are not enforcement proof

Use the configured named-worker definitions, effective route and actual
host/session metadata as the acceptance scope. Changes require new acceptance.
The host still enforces whatever restrictions it supports; this feature cannot
prove that behavior. A worker summary, no observed nesting or an actor label
does not authenticate isolation or the human.

The normal human-terminal process and guard remain the decision provenance
model, as for existing gates/source consent. Reject agent actors and block
agent-tool acceptance calls even if they supply a human actor label. Do not
claim this authenticates humans against arbitrary local processes. The exact
current session identifier must be supplied by host context; equality with it
is an operational consistency check, not authenticated session detection.

## Decision: No self-bootstrap exception

The frozen selective route has no workers in implementation. Feature 041 is
implemented in the host, without invoking the conductor or exercising the
future missing-evidence exception. Its named plan reviewer follows the current
selective operational-review procedure, not hybrid no-tool certification.
Unavailable capabilities still stop that route. No new acceptance is recorded
or implied for 041 as part of this bootstrap.

## Decision: Do not expand the hybrid adapter

The existing adapter only supports `hybrid-plan` and validates a no-tool review
boundary. Its strict checks remain unchanged. Reading logs, inventing ordinary
worker certification, adding hooks or changing native tool permissions would
expand scope without solving the absence of an exposed trusted tool inventory.

## Decision: No application-security relaxation

The receiving constitution prohibits prompts/tool visibility as authorization
boundaries. This change only records a development operator's accepted lack of
isolation evidence. Work that requires verified isolation remains ineligible;
application authorization, credentials and data policy are unchanged.
