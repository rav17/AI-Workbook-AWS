# AI-DLC extras pack

Adds, when enabled:

- stages `market-research` (after ideation, led by `product`), `nfr-design` (after plan, led by `architect`) and `perf-validation` (after implement, led by `quality`). All are optional;
- profiles `discovery` and `nfr-hardening` that use them;
- a required `nfr-section` sensor for `nfr-hardening`: the plan needs a non-empty `Non-functional requirements` section before the `nfr-design` gate.

## Enable

1. Set `"enabled": true` in `plugin.json` (a human edit).
2. Run `python -m speckit_flow plugins validate`, then `python -m speckit_flow stages` and `profiles`.

Stages are read once when the tool starts, so enabling or disabling takes effect in the next command run.

## Templates

`templates/` holds a starting layout for each new stage's artifact. The tool does not read them; the stage's lead agent uses them through the stage description.

## Adapt

Edit `stages.json` to change anchors or leads, or add stages the same way. A stage must be optional and have an existing core domain agent as its lead.
