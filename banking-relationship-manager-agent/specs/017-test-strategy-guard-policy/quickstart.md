# Quickstart: Test Strategy and Guard Policy

1. Copy a profile into `.specify/custom/profiles/strict-feature.json` with `"guard_policy": "strict"` and a matching id.
2. Init a feature with it and reach the `specify` gate. `gate approve specify --actor human:you` is refused until a current review exists and no questions are open.
3. Add `"test_strategy": "required"`. Approving the `tasks` gate is refused while an `FR-###` has no test task (`trace --require-tests` shows the gaps).
4. Run `python -m pytest tests/unit/speckit_flow/test_flow_policy_questions.py -q`.
