# Feature 024: Custom and plugin agents

## Requirements

- **FR-001**: Extra agents load from `.specify/custom/agents.json` and from enabled plugins' `agents.json`, merged after the core roster.
- **FR-002**: Extras are add-only: no core id reuse, `domain` role only, and no stage leads.
- **FR-003**: Core role counts are validated against core agents only.
- **FR-004**: The conductor must list every core agent and may list extras; it cannot list unknown agents.
- **FR-005**: Each agent reports its `source` (`core`, `custom`, `plugin:<name>`).

## Plan

`speckit_flow/agents.py`: add `Agent.source`, `_extra_sources`, merge in `load_roster`, adjust `validate_roster`. Guard already protects `.specify/custom/` and `.specify/plugins/`.

## Tasks

- [x] T001 Merge extras in `load_roster` (FR-001, FR-002, FR-005)
- [x] T002 Core-only count and conductor check (FR-003, FR-004)
- [x] T003 Tests in `test_flow_extra_agents.py` (FR-001, FR-002, FR-003)
- [x] T004 Docs section (FR-001)
