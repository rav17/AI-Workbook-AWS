# CLI Contract

- `intents list` - one line per feature: `* name profile stage gate [parked]`; `*` marks the active one. `--json` supported.
- `intents switch <name>` - set active pointer; error if not initialized.
- `intents park [--reason R]`, `intents unpark` - act on `--feature-dir` or the active feature.
- `redo <stage> --reason R` and `jump <stage> --reason R` - human only; exit 1 with an audited failure otherwise.
- `stage start` on a parked feature exits 1.
- `scripts/speckit_session.py` - prints `speckit: active=<name> stage=<s> lead=<agent> [parked]`; exit 0 always.
