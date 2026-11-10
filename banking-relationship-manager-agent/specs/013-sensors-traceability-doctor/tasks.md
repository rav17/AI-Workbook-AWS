# Tasks: Sensors, Traceability and Doctor

- [x] T001 [US1] FR-001 FR-006 Add `sensor_run` event type in `speckit_flow/models.py` and sensor config loading/validation in `speckit_flow/sensors.py`
- [x] T002 [US1] FR-002 FR-003 FR-004 Implement builtin and command sensors, result storage and `run_stage` in `speckit_flow/sensors.py`
- [x] T003 [US1] FR-005 FR-009 Enforce required sensors in `decide_gate` in `speckit_flow/state.py`
- [x] T004 [US2] FR-007 Implement `speckit_flow/trace.py`
- [x] T005 [US3] FR-008 Implement `speckit_flow/doctor.py`
- [x] T006 FR-004 FR-007 FR-008 Wire `sensors`, `trace`, `doctor` and `--sensors-file` into `speckit_flow/cli.py`
- [x] T007 FR-001 Add default `.specify/sensors/sensors.json`
- [x] T008 FR-010 Extend `scripts/speckit_guard.py` protection to sensor files
- [x] T009 [US1] FR-005 Add test for gate enforcement in `tests/unit/speckit_flow/test_flow_sensors.py`
- [x] T010 [US2] FR-007 Add test for traceability in `tests/unit/speckit_flow/test_flow_trace.py`
- [x] T011 [US3] FR-008 Add test for doctor in `tests/unit/speckit_flow/test_flow_doctor.py`
- [x] T012 FR-010 Add test for guard protection in `tests/unit/speckit_flow/test_flow_guard.py`
- [x] T013 Update `docs/speckit-profiles.md`, run ruff, mypy, full tests, `graphify update .`
