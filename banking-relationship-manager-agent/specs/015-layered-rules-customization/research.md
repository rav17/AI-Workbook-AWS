# Research: Layered Rules and Customization Overlay

- **Decision:** layers are sibling files (`org.json`, `team.json`, `rules.json`) rather than a nested schema. **Why:** reuses `load_rules` and its validation unchanged. **Alternative:** one file with a `layer` field (rejected; harder to protect and review per layer).
- **Decision:** overlay merges by id and reuses the core validators. **Alternative:** a separate overlay schema (rejected; duplicates validation).
- **Decision:** a required core sensor cannot be replaced by an overlay at all. A first version allowed replacement if the overlay stayed required with the same stages; review showed that still let an overlay swap the check's implementation.
- **Decision:** phase-level rules reuse existing stage-origin matching rather than a fourth layer.
