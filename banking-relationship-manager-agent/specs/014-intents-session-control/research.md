# Research

- **Decision**: Derive parked status from the audit trail. **Rationale**: no schema change to `state.json`, single source of truth, tamper-evident. **Alternatives**: parked flag in state (migration needed).
- **Decision**: Intents are the existing feature directories; the active one is `.specify/feature.json`. **Rationale**: reuses Spec Kit's own pointer so every skill follows the switch.
- **Decision**: Redo is human-only and resets the stage plus all later stages. **Rationale**: downstream approvals become invalid when upstream is redone. **Alternatives**: reset only the target stage (leaves stale approvals).
- **Decision**: No forward jump. **Rationale**: it would bypass gates and sensors.
- **Decision**: `sessionStart` hook is best-effort, always exit 0. Copilot hook docs do not guarantee that output is injected into context.
