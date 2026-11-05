# CLI Contract (additions to 009)

Same global options as 009 (`--feature-dir`, `--actor`, `--json`). Failures exit non-zero with a one-line error and, where a feature is in scope, a `failure` audit event.

| Command | Behavior |
|---|---|
| `review save <stage> --file review.json` | Validate a review (schema, citations, verdict rules, fingerprint, reviewer != author, redaction), assign id, save to `reviews/`, audit `review_recorded` with id and verdict. |
| `review list [<stage>]` | List reviews with verdict and stale flag. |
| `gate approve <stage> [--override-reason R]` | (extends 009) Uses the latest non-stale review. Comprehensive depth with no valid review: refused. Verdict `block`: refused unless `--override-reason`, then audit `gate_overridden`. Approval detail includes `review=<id>`. |
| `rules propose --text T --from-gate <stage> | --from-finding <review-id>:<n> | --manual` | Store a `pending` rule, audit `rule_proposed`. |
| `rules approve|discard <id>` | Requires a `human:` actor; updates status, audit `rule_approved` / `rule_discarded`. |
| `rules list [--status S] [--stage X]` | List rules; `--stage` returns active rules relevant to the stage (capped at 10), conflicts flagged. |
| `knowledge list [--stage X]` | Titles and paths of knowledge docs for the stage; reports "no knowledge found" when empty. |
| `compose validate --file route.json` | Validate a proposed route; prints the broken rule on failure. |
| `compose save --file route.json --confirm` | Write `route.json` to the feature, initialize state from it, audit `route_composed`. Requires `--confirm`. |
| `init --route-file route.json` | Equivalent to compose save for a new feature. |

Schemas: [review.schema.json](./review.schema.json), [rule.schema.json](./rule.schema.json). Profile schema from 009 is updated for the new stage names.
