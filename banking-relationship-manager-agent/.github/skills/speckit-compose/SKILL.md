---
name: "speckit-compose"
description: "Compose a custom workflow route (stages, depth, gates, reasons) when no shipped profile fits; validated by code and saved only after confirmation."
compatibility: "Requires spec-kit project structure with .specify/ directory and the speckit_flow package"
metadata:
  author: "project"
  source: "specs/010-reviewers-rules-knowledge"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The argument describes the work.

## Procedure

1. Run `python -m speckit_flow profiles suggest "<description>"` and `profiles list`. If a shipped profile fits, use it (skill `speckit-profile`) and stop.
2. Otherwise draft a route as JSON in the session scratch area:

   ```json
   {
     "id": "custom-<feature-folder-name>",
     "description": "...",
     "stages": ["specify", "plan", "implement"],
     "depth": "standard",
     "gates": ["plan"],
     "exemptions": ["implement-without-tasks"],
     "reasons": {"specify": "why", "plan": "why", "implement": "why"}
   }
   ```

   - Stages (canonical order): `ideation, specify, clarify, plan, tasks, analyze, implement, deploy, operate`.
   - `specify` comes first (optionally after `ideation`); `implement` needs `tasks` unless `implement-without-tasks` is declared; `deploy` needs `implement`; `operate` needs `deploy`; gates must be stages in the route.
   - Every stage needs a reason.
3. Validate: `python -m speckit_flow compose validate --file <path>`. Fix and repeat until valid.
4. Show the user the route and every reason. **Only after explicit confirmation**, save it:
   `python -m speckit_flow compose save --file <path> --confirm --actor human:<name>`
   (or `init --route-file <path>`). This initializes state and records `route_composed` in the audit trail.
5. Continue with the `speckit-profile` procedure.

## Rules

- Never save without the user's confirmation. Reasons must not contain secrets.
- Composition is the `speckit-composer` agent's role. Show each stage's default lead with `python -m speckit_flow agents assign --profile <id>`; routes may override via `assignments`.
