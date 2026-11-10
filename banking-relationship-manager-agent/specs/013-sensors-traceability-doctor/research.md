# Research: Sensors, Traceability and Doctor

- **Decision**: Sensors are defined in a version-controlled JSON file, run without a shell. **Rationale**: deterministic, reviewable, avoids command injection. **Alternatives**: arbitrary shell strings (rejected, injection risk); plugin system (over-scoped).
- **Decision**: Results store artifact fingerprints (spec/plan/tasks) and reuse the review staleness idea. **Rationale**: approving on stale evidence is the main risk. **Alternatives**: timestamps only (rejected, weaker).
- **Decision**: Do not store command output. **Rationale**: avoid leaking secrets into audit or results.
- **Decision**: Gate enforcement is active only when the config file exists. **Rationale**: backward compatibility.
- **Decision**: Traceability is by `FR-###` citation text, tests identified by the word `test` in the task line. **Rationale**: matches the repo's existing spec and tasks templates; no new syntax. **Alternatives**: explicit mapping file (extra maintenance).
- **Decision**: `doctor` is read-only and never writes audit events.
