# Plan: Clarify Interaction Modes (021)

- Add an "Interaction modes and the questions file" section to `.github/skills/speckit-clarify/SKILL.md` ahead of the execution steps (FR-001 to FR-004). The original loop is untouched (FR-005).
- Add `tests/unit/speckit_flow/test_flow_clarify_skill.py` to guard the section so a skill refresh does not silently drop it.
- Decision: no new CLI code; features 016-017 already provide add, answer, list, check, the guard and the sensor.
- Risk: `specify` upgrades may overwrite the skill; the test fails loudly if so.
