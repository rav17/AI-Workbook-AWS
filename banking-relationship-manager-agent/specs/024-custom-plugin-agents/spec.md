# Feature 024: Custom and plugin agents

## Requirements

- **FR-001**: Extra agents load from `.specify/custom/agents.json` and from enabled plugins' `agents.json`, merged after the core roster.
- **FR-002**: Extras are add-only: no core id reuse, `domain` role only, and no stage leads.
- **FR-003**: Core role counts are validated against core agents only.
- **FR-004**: The conductor must list every core agent and may list extras; it cannot list unknown agents.
- **FR-005**: Each agent reports its `source` (`core`, `custom`, `plugin:<name>`).
