# Feature Specification: Ceremony Toggles

**Feature**: 022-ceremony-toggles
**Status**: Implemented

## User Story 1 - Profiles switch optional ceremony off (P1)
- **FR-001**: A profile MAY set `ceremony` with boolean keys `learning` and `reviews`; each defaults to on. Unknown keys and non-boolean values MUST be refused.
- **FR-002**: With `learning` off, `rules propose` for a feature on that profile MUST be refused.
- **FR-003**: A strict guard policy (explicit, or implied by comprehensive depth) MUST NOT be combined with `reviews` off.
- **FR-004**: Sensors, gates, the roster check and the guard policy MUST never be switchable.
- **FR-005**: The `bugfix` profile MUST skip `learning` and keep everything else.
- **FR-006**: The session summary MUST show switched-off items as `skips=`; the conductor MUST treat `reviews` off as making the reviewer dispatch optional.

## Out of scope
More toggles (knowledge surfacing, questions); enforcing `reviews` off beyond guidance.
