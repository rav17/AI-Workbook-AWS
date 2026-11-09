# Quickstart: Structured Stage Contracts

## Prerequisites

- Python 3.11 and the repository's existing development dependencies.
- A disposable receiving-project fixture for acceptance checks.
- Human approval of the verification command before using it as a construction
  checkpoint.

## Proposed verification command

After human approval, run the focused contract, sensor, gate and portability
tests:

```powershell
pytest tests/unit/speckit_flow/test_flow_contracts.py tests/unit/speckit_flow/test_flow_cli_contracts.py tests/unit/speckit_flow/test_flow_sensors.py tests/unit/speckit_flow/test_flow_state.py tests/unit/speckit_flow/test_flow_profiles.py tests/unit/test_speckit_bootstrap.py -q
ruff check speckit_flow tests/unit/speckit_flow tests/unit/test_speckit_bootstrap.py
mypy speckit_flow
python -m speckit_flow doctor
python -m speckit_flow plugins validate
```

Do not treat this proposal as approved verification. The human must approve it
before it is used for a construction checkpoint. The profile parser and CLI
tests are included because opt-in behavior and contract inspection are part of
the feature.

## Validation scenarios

1. **Capability disabled**: validate plugins and confirm the default profile
   route and gate behavior are unchanged.
2. **Contract inspection**: enable the pack in a disposable non-banking
   project, inspect each contract in the contract-enabled profile, and verify
   purpose, inputs, outputs and acceptance criteria are present.
3. **Required output checks**: run the contract sensor for a gated stage with
   a missing or empty required output; expect failure identifying that output.
4. **Gate freshness**: produce all required outputs and run the sensor; change
   one output; attempt approval and expect stale evidence to block it. Re-run
   the sensor and verify only a human can approve.
5. **Non-gated advisory**: omit a required output at a non-gated stage; verify
   the sensor reports the gap but stage completion remains available.
6. **Path safety**: verify absolute paths, traversal, symlinks, inaccessible
   files, excessive output lists and oversized files fail explicitly.
7. **Project customization**: add a valid contract for a custom stage in the
   fixture; verify the project contract is applied without changing the
   portable defaults.

## Expected outcome

All required-output checks are deterministic and feature-local. Human review
assesses meaning and acceptance criteria; no source-project commands, live
services, credentials or artifact contents are inherited or executed.

## Verification results

The approved verification command completed successfully:

- Focused pytest selectors: **93 passed, 1 skipped**. The skipped case requires
  symlink creation, unavailable in this Windows environment.
- Ruff: **all checks passed**.
- Mypy: **no issues found in 24 source files**.
- `python -m speckit_flow doctor`: **passed**; the feature check was skipped
  because no feature directory is initialized.
- `python -m speckit_flow plugins validate`: **passed**; all 6 plugin manifests
  validated, including the disabled `stage-contracts` plugin.
- `graphify update .`: **completed**.
