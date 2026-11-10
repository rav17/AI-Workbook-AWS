# Plan: Stages as Data (018)

- New `speckit_flow/stagedefs.py` loads and validates the core file plus overlay (FR-001, FR-005, FR-006).
- `models.py` builds `STAGE_DEFS`, `STAGES`, `OPTIONAL_STAGES`, `STAGE_REQUIRES`, `STAGE_LEADS`, `FIRST_STAGE` at import; `Profile.validate` uses them (FR-002, FR-004).
- `state.py` imports `OPTIONAL_STAGES` from models; `agents.py` accepts a stage `lead` (FR-007).
- `cli.py` adds `stages`; `doctor.py` adds a stages check; guard protects `.specify/stages/` (FR-008, FR-009).
- Decision: stages load once at import. Changing stages needs a new process, which matches CLI use and keeps ordering constants simple.
- Alternative rejected: runtime-mutable stage registry (more state, no current need).
