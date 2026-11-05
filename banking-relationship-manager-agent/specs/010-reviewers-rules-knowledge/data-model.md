# Data Model

## Stage list (extends 009)
Canonical order: `ideation, specify, clarify, plan, tasks, analyze, implement, deploy, operate`.
Rules: `specify` is first unless `ideation` precedes it (then `ideation` is first); `implement` requires `tasks` unless exempted; `deploy` requires `implement`; `operate` requires `deploy`. All 009 profiles remain valid.

## Review (`<feature>/reviews/<stage>-<n>.json`)
| Field | Type | Rules |
|---|---|---|
| id | string | `<stage>-<n>`, n increments per stage |
| stage | string | stage in the feature's route |
| reviewer | string | `spec`, `plan` or `code` |
| author | string | role/agent that produced the stage output; must differ from reviewer |
| verdict | enum | `pass`, `concerns`, `block` |
| findings | list of Finding | may be empty only when verdict is `pass` |
| files | map path → sha256 | non-empty; every path relative and existing at save time |
| created_at | ISO-8601 UTC | |

**Finding**: `{severity: info|warning|major|blocker, file: string, section: string, note: string (max 500)}`. `file` must be a key of `files`; `section` non-empty. Any `blocker` forces verdict `block`; verdict `pass` is invalid with `major` or `blocker`. `note` passes the redaction check.

Staleness: a review is stale when any recorded hash differs from the current file content. Stale reviews do not satisfy gating.

## Rule (`.specify/rules/rules.json`)
| Field | Type | Rules |
|---|---|---|
| id | string | `R-<nnn>` |
| text | string | 1-300 chars, redaction-checked |
| origin | string | `gate:<feature>:<stage>` or `finding:<feature>:<review-id>:<n>` or `manual` |
| status | enum | `pending`, `active`, `discarded` |
| proposed_at | ISO-8601 UTC | |
| decided_by | string or null | must start with `human:` for approve/discard |

Transitions: pending → active, pending → discarded; active → discarded. No other transitions.

## KnowledgeDoc (derived from `.specify/knowledge/*.md`)
`{path, title, stages}`; title from a `title:` line else the filename; `stages` from a `stages:` line (`all` default).

## Route (`<feature>/route.json`)
Same fields as Profile (id `custom-<feature>`), plus `reasons: {stage: string}` with an entry for every stage. State records `profile = custom-<feature>`.

## Audit additions
New event types: `review_recorded`, `gate_overridden`, `rule_proposed`, `rule_approved`, `rule_discarded`, `route_composed`. Gate approval `detail` includes `review=<id>` when a review was relied on.
