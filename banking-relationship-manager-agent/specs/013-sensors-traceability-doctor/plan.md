# Implementation Plan: Sensors, Traceability and Doctor

**Branch**: `013-sensors-traceability-doctor` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

## Summary

Add `speckit_flow/sensors.py` (config, builtin and command sensors, result storage, gate check), `speckit_flow/trace.py` (requirement/task/test matrix) and `speckit_flow/doctor.py` (health checks). `state.decide_gate` gains an optional `sensors_file`; the CLI passes the default file when it exists. New CLI commands: `sensors list|run`, `trace`, `doctor`. New audit event `sensor_run`. The guard hook protects sensor results and configuration.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only. **Storage**: `.specify/sensors/sensors.json`; results in `<feature>/sensors/<stage>.json`. **Testing**: pytest. **Constraints**: no shell execution, no stored command output, backward compatible when config absent.

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Structured state authoritative | PASS: results are structured JSON with fingerprints. |
| II. Deterministic safety | PASS: gate refusal is enforced in code. |
| III. Patch, validate, invalidate | PASS: stale results are invalidated by fingerprint. |
| IV. Bounded tool use | PASS: argv-only commands with timeouts. |
| V. Durable boundaries | PASS: config and results live in files. |
| VI. Python quality | PASS: typed, tested, ruff/mypy. |
| Security | PASS: output never stored; guard protects evidence. |

## Project Structure

```text
specs/013-sensors-traceability-doctor/  spec.md plan.md research.md data-model.md quickstart.md tasks.md contracts/cli.md
speckit_flow/  sensors.py trace.py doctor.py  (+ models.py event type, state.py gate check, cli.py commands)
.specify/sensors/sensors.json
scripts/speckit_guard.py
tests/unit/speckit_flow/test_flow_sensors.py test_flow_trace.py test_flow_doctor.py
```
