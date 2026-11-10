# Feature Specification: AI-DLC extras pack

**Status**: Implemented

## Requirements

- **FR-001**: The pack MUST live entirely in `.specify/plugins/aidlc-extras/` and ship disabled; core stages stay at 9.
- **FR-002**: Enabled, it MUST add optional stages `market-research`, `nfr-design` and `perf-validation`, each anchored with `after` and led by a core domain agent.
- **FR-003**: It MUST add profiles `discovery` and `nfr-hardening` that use those stages.
- **FR-004**: It MUST add a required `nfr-section` sensor scoped to `nfr-hardening` at stage `nfr-design`.
- **FR-005**: It MUST include a template per new stage and a README explaining enable and adapt.
- **FR-006**: Disabled, it MUST add nothing; enabled, `doctor` MUST report no failures.

## Success criteria

- **SC-001**: `stages`, `profiles list` and `doctor` show the additions only when enabled.
