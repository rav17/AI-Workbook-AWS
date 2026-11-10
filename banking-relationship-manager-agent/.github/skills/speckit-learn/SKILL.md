---
name: "speckit-learn"
description: "Propose reusable rules from gate rejections or review findings; only a human can activate them."
compatibility: "Requires spec-kit project structure with .specify/ directory and the speckit_flow package"
metadata:
  author: "project"
  source: "specs/010-reviewers-rules-knowledge"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Procedure

1. Identify a lesson: a rejected gate (`gate_rejected` in `audit.jsonl`), a repeated or major review finding, or a manual team convention the user states.
2. Write one short, imperative, general rule (max 300 characters). No secrets, identifiers or customer data; the tool rejects suspicious text.
3. Propose it (it is stored as `pending`; it affects nothing yet):
   - `python -m speckit_flow rules propose --text "<rule>" --from-gate <stage> --actor agent:<name>`
   - or `--from-finding <review-id>:<n>` (for example `plan-1:2`), or `--manual`.
4. Show the user the pending rule and ask them to approve or discard it. Never approve on their behalf. A human runs:
   `python -m speckit_flow rules approve <R-nnn> --actor human:<name>` (or `discard`).
5. Review the list with `python -m speckit_flow rules list [--status pending|active|discarded]`. Rules marked CONFLICT contradict each other; ask the user which to keep (discard the other).

## Rules

- Do not propose duplicates; check `rules list` first.
- Active rules for a stage are shown with `rules list --stage <stage>` (capped at 10).
