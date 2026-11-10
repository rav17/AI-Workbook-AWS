# Quickstart: Compliance Plugin Pack

Prerequisite: run from `banking-relationship-manager-agent/`.

1. **Disabled by default** (US1 scenario 2, FR-006)
   - `python -m speckit_flow plugins list` shows `compliance` as disabled.
   - `python -m speckit_flow profiles` does not list `compliance`.
2. **Enable** (US1)
   - Set `"enabled": true` in `.specify/plugins/compliance/plugin.json` (a human edit).
   - `python -m speckit_flow plugins validate` passes; `profiles` now lists `compliance`.
3. **Sensor blocks the gate** (US2, SC-003)
   - Initialize a feature with `--profile compliance`, write a plan without a Compliance heading, run `sensors run plan`, then try `gate approve plan`. Expect a refusal naming `compliance-section`.
   - Add a `## Compliance` section with content, re-run the sensor, approve. Expect success.
4. **Agent listed** (US3)
   - `python -m speckit_flow agents list` shows `compliance-reviewer` with source `plugin:compliance`.
5. **Doctor** (SC-004): `python -m speckit_flow doctor` has no failures enabled or disabled.
6. **Automated**: `python -m pytest tests/unit/speckit_flow/test_flow_compliance_pack.py -q`.
