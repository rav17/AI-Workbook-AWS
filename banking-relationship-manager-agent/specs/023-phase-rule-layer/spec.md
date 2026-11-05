# Feature 023: Phase rule layer

## Requirements

- **FR-001**: Rules support a fourth, narrowest layer `phase`, stored at `.specify/rules/phase/<stage>.json`.
- **FR-002**: The phase layer applies only when a stage is requested and its file exists.
- **FR-003**: A phase rule overrides an opposite-polarity rule from any wider layer.
- **FR-004**: Phase rule files are protected from agent writes by the guard hook.

## Plan

Extend `LAYERS` and `_layer_path` in `speckit_flow/rules.py`; extend `_PROTECTED` in `scripts/speckit_guard.py`.

## Tasks

- [x] T001 Add phase layer to `rules.py` (FR-001, FR-002, FR-003)
- [x] T002 Protect phase files in the guard (FR-004)
- [x] T003 Tests in `test_flow_phase_rules.py` (FR-001, FR-002, FR-003, FR-004)
- [x] T004 Document in `docs/speckit-profiles.md` (FR-001)
