# Tasks: Layered Rules and Customization Overlay

- [x] T001 [US1] Add `effective_rules` with org/team/project layers in speckit_flow/rules.py for FR-001, FR-002
- [x] T002 [US1] Add `rules list --effective` in speckit_flow/cli.py for FR-001
- [x] T003 [US2] Merge overlay profiles in speckit_flow/profiles.py for FR-003
- [x] T004 [US2] Merge overlay sensors, refusing to replace required core sensors, in speckit_flow/sensors.py for FR-003, FR-004
- [x] T005 [US2] Add speckit_flow/custom.py and `custom list|validate` for FR-003
- [x] T006 Add `custom` check and effective-rule count to doctor for FR-005
- [x] T007 Protect `.specify/custom/`, org.json, team.json in scripts/speckit_guard.py for FR-006
- [x] T008 Test tests/unit/speckit_flow/test_flow_layers_custom.py and test_flow_cli_015_017.py for FR-001, FR-002, FR-003, FR-004, FR-005, FR-006
- [x] T009 Document in docs/speckit-profiles.md for FR-003
