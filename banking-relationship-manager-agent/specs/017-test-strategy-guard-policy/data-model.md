# Data Model: Test Strategy and Guard Policy

`Profile` gains:
- `test_strategy`: `standard` (default) or `required`.
- `guard_policy`: `""` (derived), `standard` or `strict`.
- `strict` (derived property): explicit strict, or comprehensive depth when `guard_policy` is unset.

Both fields are omitted from serialized profiles when at their defaults. Gate approval checks run in `state.decide_gate`.
