# Data Model: Structured Stage Contracts

## StageContract

Describes the work agreement for one stage.

| Field | Type | Rules |
|---|---|---|
| `stage` | string | Existing stage identifier; unique across the resolved contract set. |
| `purpose` | string | Non-empty, human-readable outcome for the stage. |
| `inputs` | list of ContractInput | Each item has a non-empty `id` and `description`; inputs guide work but are not automatically validated. |
| `outputs` | list of ContractOutput | Each item has a non-empty `id` and `description`, and a `required` boolean. |
| `acceptance_criteria` | list of strings | At least one non-empty, reviewable criterion. |
| `review_focus` | list of strings | Reviewer prompts; may be empty. |

## ContractInput

| Field | Type | Rules |
|---|---|---|
| `id` | string | Unique within the contract. |
| `description` | string | Non-empty; may identify an expected artifact or decision. |
| `path` | string, optional | If present, a canonical feature-relative path. This is informational and does not imply a file check. |

## ContractOutput

| Field | Type | Rules |
|---|---|---|
| `id` | string | Unique within the contract. |
| `description` | string | Non-empty expected deliverable. |
| `required` | boolean | Required outputs are checked only when they have a declared path and a gate sensor is run. |
| `path` | string, optional | Canonical feature-relative file path, bounded to 100 unique paths and 1 MiB per file. |

For every required output in a gated stage, `path` is mandatory. Optional
outputs and required outputs in non-gated stages may be descriptive only.

## ContractCheckResult

Represents one sensor run for a stage.

| Field | Type | Rules |
|---|---|---|
| `stage` | string | Stage associated with the sensor run. |
| `status` | enum | `pass` or `fail`. |
| `timestamp` | ISO timestamp | Recorded by the existing audit/sensor lifecycle. |
| `reason` | string | Bounded explanation identifying missing or invalid outputs without file contents. |
| `fingerprints` | map of path to digest | Current hashes for declared contract and required output files; used to detect stale evidence. |

## Profile contract opt-in

Workflow profiles have an optional `stage_contracts` boolean. It defaults to
`false`; when `true`, all routed stages must have resolved contracts and all
required outputs on gated stages must have checkable paths. The plugin's
`contract-driven` profile sets it to `true`. Existing profile files need no
changes.

## Resolution and state transitions

1. Load built-in plugin contracts, then project-owned overrides.
2. Validate every contract and reject duplicate/unknown stage IDs.
3. Before an opted-in profile starts, ensure each routed stage has a contract;
   gated stages must have machine-checkable required outputs.
4. A sensor run evaluates current required outputs and saves its result.
5. Human approval is allowed only if required sensor evidence passed and its
   fingerprints still match. The existing human gate remains the sole approval
   authority.

No artifact contents are copied into the contract result or audit trail.
