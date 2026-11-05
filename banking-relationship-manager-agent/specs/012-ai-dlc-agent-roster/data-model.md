# Data Model: AI-DLC Agent Roster

## Agent (roster entry)
| Field | Rule |
|-------|------|
| `id` | Lowercase kebab name, unique (e.g. `architect`). Actor form: `agent:<id>`. |
| `role` | `domain`, `reviewer`, `composer` or `conductor`. |
| `tier` | `judgment`, `templated` or `balanced`. |
| `file` | Path to `.github/agents/speckit-<id>.agent.md`; must exist. |
| `leads` | Stages the agent leads; each stage in `STAGES`. Only domain agents may lead. |
| `supports` | Stages the agent supports; each stage in `STAGES`. |
| `can_edit` | Boolean; must be `false` for reviewers and the composer. |

Roster rules: exactly 11 domain, 2 reviewer, 1 composer, 1 conductor; names unique; every stage has exactly one lead; reviewer and composer agent files must not grant `edit`; domain agents must not grant `agent`; the conductor must list every roster agent in `agents`.

## Stage assignment
`{stage: {lead: <id>, support: [<id>...]}}` resolved from the roster for each stage in a profile's route. A profile may include an `assignments` block with the same shape; its agents must exist in the roster and its stages must be in the profile's route.

## Agent actor
`agent:<id>` where `<id>` is in the roster. Unknown ids are refused for agent-restricted actions. Gate decisions and rule decisions accept only `human:` actors.

## Profile change
`assignments` is a new optional field (default empty). Profiles without it load unchanged.
