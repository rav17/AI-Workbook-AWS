---
name: "speckit-profile"
description: "Select, confirm, switch and track a workflow profile (feature, bugfix, enterprise, ...) for the current feature, with persistent state and an append-only audit trail."
compatibility: "Requires spec-kit project structure with .specify/ directory and the speckit_flow package"
metadata:
  author: "project"
  source: "specs/009-workflow-profiles-audit"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

Right-size the Spec Kit ceremony for the kind of work. Each profile in `.specify/profiles/*.json` declares its stage route, depth and approval gates. State lives in `<feature>/state.json` (rendered as `state.md`); every decision is appended to `<feature>/audit.jsonl`. The helper is `python -m speckit_flow`; always run it from the repository root. Never edit `state.json` or `audit.jsonl` by hand.

## Procedure

1. **Choose a profile**
   - Use `speckit-workflow` for new requests or execution. It runs `python -m speckit_flow workflow recommend "<description>" --json`; pass `--profile <id>` for an explicit selection. An ambiguous request requires a question, not a silent fallback.
   - **Always ask the user to confirm** before initializing. New features recommend `full-lifecycle`, bugs/hotfixes `bugfix`, security fixes `security-patch`. Preserve an already initialized feature's route.
   - Unknown names: show the valid profiles and stop.

2. **Initialize** once the confirmed entry skill has allocated the feature directory (before ideation when that stage is routed):
   `python -m speckit_flow init --profile <id> --actor agent:conductor`
   Stages omitted by the profile are recorded as skipped with a reason.

3. **Run only the stages in the route**, in order. Around each stage:
   - Use `speckit-workflow` to run dispatch preflight and invoke the conductor. Do not execute stage bodies in the caller; the conductor owns start/done, assigned lead dispatch and the recursion-safe stage brief.
   - If the profile gates the stage (`pending_gate` is set), ask the human to approve or reject, then record it with `gate approve <stage>` or `gate reject <stage> --reason "<short reason>"`. Use `--actor human:<name>` for human decisions. Do not start the next stage while a gate is pending.
   - Honor depth: `minimal` means brief artifacts, `comprehensive` means full detail and all checklists.

4. **Switching profiles** is allowed only at a stage boundary and needs explicit user confirmation:
   `python -m speckit_flow switch --profile <id> --confirm`

5. **Reviews, knowledge and rules** (features 010):
   - Before starting a stage run `python -m speckit_flow knowledge list --stage <stage>` and open only the relevant documents, and `python -m speckit_flow rules list --stage <stage>` and follow the active rules (flag any marked CONFLICT to the user).
   - Before a gated approval run the `speckit-review` skill. `comprehensive` depth refuses approval without a current review; a `block` verdict needs `gate approve <stage> --override-reason "<why>"` from a human.
   - After a rejected gate or a repeated finding, offer the `speckit-learn` skill to propose a rule. Never approve rules yourself.
   - For work that fits no profile, use the `speckit-compose` skill. `full-lifecycle` adds `ideation`, `deploy` and `operate` stages (templates: `ideation-template.md`, `release-template.md`, `runbook-template.md`).

6. **Resuming**: run `python -m speckit_flow resume`. If `state.json` is missing or corrupt, tell the user and offer `python -m speckit_flow rebuild`. If `status` reports an audit integrity problem, report it and stop.

## Rules

- Keep `--reason` and other free text short and free of secrets, credentials or customer data; the tool rejects text that looks sensitive.
- If a command fails, show the error to the user; do not continue silently and do not work around the audit trail.
- Without an initialized profile, use the confirmed profile-aware entry flow. The legacy `init` default remains `feature` for explicit CLI clients, not an automatic selection policy.
- `status`/`resume` report `lead_agent` for the next stage. Delegate that stage to the matching `speckit-<id>` agent through the `speckit-conductor` agent, and record work with `--actor agent:<id>`. Never approve or reject gates as an agent; only a `human:` actor may.
