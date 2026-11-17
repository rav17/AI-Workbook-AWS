# Specification: lean workflow validation

## User scenario

A developer resumes a feature using compact context and checks that tasks cover
its requirements. Invalid trace input must not look successful. Quick planning
should not suggest unnecessary documents or unrelated architecture layouts.

## Requirements

- FR-001: Trace rejects a specification without requirement IDs, a task list
  without task entries, and duplicate task IDs. Unknown requirement references
  fail trace success checks and produce useful CLI/sensor/gate diagnostics.
- FR-002: Context and dispatch validate and inspect audit integrity, nonemptiness
  and parked status in a single fresh file read per call; preserve tamper and
  invalid-input failures. No persistent cache or skipped chain verification.
- FR-003: Reduce the plan template by at least 25 percent in UTF-8 bytes from
  its measured 3,682-byte baseline, retaining technical context, constitution,
  actual structure and complexity sections. Mark quick auxiliary artifacts
  conditional; do not remove richer-profile artifacts required by policy.
- FR-004: Preserve profiles, gates, human authority, tests/sensors, portability
  and existing uncommitted changes. No new stage, agent, dependency or scheduler.

## Evidence and boundaries

Scan reproduced three false passes: no requirements, unknown references and
duplicate task IDs. One context invocation opened audit.jsonl three times.
No application behavior or live systems are in scope. This is a bounded
improvement batch, not a complete audit or an end-to-end speed/accuracy claim.
Unknown refs becoming errors and legacy invalid traces failing are intentional.
