---
name: "speckit-review"
description: "Independent spec, plan or code review that cites files and sections and is bound to file fingerprints, so approvals rest on current evidence."
compatibility: "Requires spec-kit project structure with .specify/ directory and the speckit_flow package"
metadata:
  author: "project"
  source: "specs/010-reviewers-rules-knowledge"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The argument is the stage to review (for example `specify`, `plan`, `implement`).

## Roles

| Reviewer | Reviews | Looks for |
|----------|---------|-----------|
| `spec` | spec.md (and clarifications) | ambiguity, untestable requirements, missing edge cases, scope creep |
| `plan` | plan.md, data-model.md, contracts/ | constitution violations, missing decisions, unsafe design, gaps vs spec |
| `code` | changed source and tests | bugs, missing tests, security issues, deviations from plan |

## Procedure

1. Pick the role matching the stage. Read only the artifacts that role needs.
2. Review with fresh eyes: you must **not** be the author of the output. Set `author` to whoever produced it (for example `agent:copilot`); the tool rejects a reviewer equal to the author.
3. Write a JSON file in the session scratch area (not the repo):

   ```json
   {
     "reviewer": "spec",
     "author": "agent:copilot",
     "verdict": "pass | concerns | block",
     "files": ["spec.md"],
     "findings": [
       {"severity": "info|warning|major|blocker", "file": "spec.md", "section": "Requirements", "note": "short, specific, no secrets"}
     ]
   }
   ```

   - `files` are paths relative to the feature folder (or the repo root for code). Fingerprints are computed by the tool.
   - Every finding **must** cite a reviewed file and a section. Notes are at most 500 characters and must not contain secrets or customer data.
   - Any `blocker` forces `block`. `pass` is invalid with `major` or `blocker`. An empty findings list is only valid for `pass`.
4. Save it: `python -m speckit_flow review save <stage> --file <path> --actor agent:<name>`.
5. Show the user the verdict and findings. If the stage has a gate, the human decides; for `block`, approval needs `--override-reason` from a human.
6. If artifacts change after the review, it is stale; re-run the review. `python -m speckit_flow review list <stage>` shows STALE.

## Rules

- Be specific and evidence-based; no finding without a citation.
- Never edit saved reviews by hand.
- Run reviews through the `speckit-product-lead` or `speckit-architecture-reviewer` agent (read-only tools); save with `--actor agent:<id>`. The reviewer must differ from the stage's lead agent.
