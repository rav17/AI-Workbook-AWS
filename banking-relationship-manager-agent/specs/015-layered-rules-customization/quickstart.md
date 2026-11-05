# Quickstart: Layered Rules and Customization Overlay

1. `python -m speckit_flow custom list` prints `no custom overlay` on a clean checkout.
2. Add `.specify/custom/profiles/team-fix.json` (copy `bugfix.json`, set `"id": "team-fix"`). `custom list` shows `profile team-fix (add)`; `profiles` lists it.
3. Add `.specify/rules/org.json` with one active rule. `rules list --effective` shows it as layer `org`.
4. Break the overlay (invalid JSON). `custom validate` and `doctor` fail with a clear error.
5. Run `python -m pytest tests/unit/speckit_flow/test_flow_layers_custom.py tests/unit/speckit_flow/test_flow_cli_015_017.py -q`.
