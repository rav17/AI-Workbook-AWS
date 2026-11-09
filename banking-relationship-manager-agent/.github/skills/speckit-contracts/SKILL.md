---
name: speckit-contracts
description: "Use when inspecting or authoring structured Spec Kit stage contracts, required outputs, or human-gate evidence."
---

# Stage Contracts

Use the contract as the working agreement for the active stage. It records
purpose, inputs, outputs, acceptance criteria and reviewer focus; it does not
replace the feature specification, plan, task list or human review.

## Inspect

- Run `python -m speckit_flow contracts list` to list installed contracts.
- Run `python -m speckit_flow contracts show <stage>` to inspect one contract.
- With `--feature-dir`, inspection is limited to the initialized,
contract-enabled profile's route.

## Work and review

- Use the declared inputs and acceptance criteria to guide the stage.
- Produce required outputs at their declared feature-relative paths.
- Run `python -m speckit_flow sensors run <stage> --actor agent:quality` to
  check path-addressable required outputs.
- A failed or stale required sensor blocks a human gate. Re-run it after
  required outputs change; only a human may approve or reject the gate.
- Non-gated stages are not blocked by this sensor. Treat its output as
  advisory.
- Presence and non-empty checks are not proof of quality. A reviewer evaluates
  meaning, completeness and acceptance criteria.

## Project-owned contracts

The optional `stage-contracts` plugin is disabled by default. Enable it only
after reviewing the pack, then use the `contract-driven` profile or set
`stage_contracts: true` on a project-owned profile. Add or override contracts
in `.specify/custom/stage-contracts.json`; each contract must name a known stage.
Every required output on a gated stage needs a safe feature-relative path.

Never put credentials, source contents or sensitive data in contracts or audit
details. The checker reads only declared files, enforces bounded file counts
and sizes, rejects symlinks and paths outside the feature directory, and does
not execute project commands.
