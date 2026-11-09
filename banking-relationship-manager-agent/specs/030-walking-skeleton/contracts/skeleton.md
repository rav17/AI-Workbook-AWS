# Contract

```text
python -m speckit_flow units add walking-skeleton "Thin journey" --tasks T001,T002 --files app.py,check.py,specs/NNN-feature/skeleton.md --actor agent:developer
python -m speckit_flow units checkpoint walking-skeleton --actor agent:developer
python -m speckit_flow sensors run walking-skeleton --actor agent:quality
```

Default receiving-project `.specify/verify.json` must be proposed by an agent
and approved by a human before checkpoint execution. No new approval command.
An explicit custom verify path remains supported by units; the profile sensor
uses the receiving project's default verification policy, not hidden overrides.

Required `skeleton` builtin at walking-skeleton, profile `skeleton-first`,
options not supported. Gate requires a current pass; normal human/order/park
checks apply. Missing/stale evidence fails. Current fingerprints include
units.json, verify policy and tracked files plus existing lifecycle artifacts.
No file content in audit; no deployment or command execution by sensor/gate.
