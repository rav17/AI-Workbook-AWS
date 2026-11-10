# CLI Contract: agents

```text
python -m speckit_flow agents list [--json]
python -m speckit_flow agents validate [--json]
python -m speckit_flow agents assign [--profile ID | --feature-dir PATH] [--json]
```

- `list`: prints each roster agent with role, tier, led and supported stages.
- `validate`: checks counts, uniqueness, files, tool scopes and the conductor allow-list. Exit 1 with one message per problem.
- `assign`: prints lead and support agents per stage for a profile id or for the feature's current profile (including a custom route). Unknown profile or agent → exit 1.

Existing commands change as follows:
- `--actor agent:<id>` must name a roster agent (or `conductor`); otherwise exit 1.
- `gate approve|reject` refuses non-human actors; the refusal is audited as a `failure` event.
- `rules approve|discard` remain human-only.
- `status` output includes the current stage's lead agent when a roster is available.
