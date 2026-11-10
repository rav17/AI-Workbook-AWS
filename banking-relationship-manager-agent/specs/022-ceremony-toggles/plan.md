# Plan: Ceremony Toggles (022)

- `models.Profile` gains `ceremony`, `ceremony_on()` and validation (FR-001, FR-003); `to_dict` round-trips it.
- `cli._require_ceremony` refuses `rules propose` when learning is off; with no state yet it allows (FR-002).
- `.specify/profiles/bugfix.json` sets `learning: false` (FR-005).
- `scripts/speckit_session.py` prints `skips=`; conductor agent text updated (FR-006).
- Decision: only two toggles, and only `learning` is hard-enforced; `reviews` is guidance because reviews are already optional unless strict. Nothing safety-related is toggleable (FR-004).
