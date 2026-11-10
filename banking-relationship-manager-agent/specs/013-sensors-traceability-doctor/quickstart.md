# Quickstart

1. `python -m speckit_flow doctor` - all checks ok.
2. `python -m speckit_flow trace --feature-dir specs/013-sensors-traceability-doctor` - matrix, no gaps.
3. `python -m speckit_flow init --profile feature --feature-dir <tmp>` then `stage start/done tasks`; `gate approve tasks` is refused until `sensors run tasks` passes.
4. `pytest tests/unit/speckit_flow -q`.
