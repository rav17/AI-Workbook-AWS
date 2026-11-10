# Feature 023: Phase rule layer

## Requirements

- **FR-001**: Rules support a fourth, narrowest layer `phase`, stored at `.specify/rules/phase/<stage>.json`.
- **FR-002**: The phase layer applies only when a stage is requested and its file exists.
- **FR-003**: A phase rule overrides an opposite-polarity rule from any wider layer.
- **FR-004**: Phase rule files are protected from agent writes by the guard hook.
