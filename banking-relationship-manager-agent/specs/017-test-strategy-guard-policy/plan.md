# Plan: Test Strategy and Guard Policy

Profile gains `test_strategy` (`standard|required`) and `guard_policy` (`standard|strict`, default derived). `Profile.strict` returns true for explicit strict, or comprehensive depth when unset. `state.decide_gate` takes an optional `profiles_dir`, resolves the profile (falling back to depth when unavailable), then enforces: required test strategy via `trace.build_matrix(...).ok(True)` at tasks/analyze/implement gates; strict policy via a current review and no open questions. Serialization omits default values so shipped profiles are unchanged.
