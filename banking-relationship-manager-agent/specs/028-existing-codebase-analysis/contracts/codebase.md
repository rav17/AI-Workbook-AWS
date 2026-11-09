# Codebase Analysis Contract

`python -m speckit_flow codebase scan [--json]`

- Scans the installed project's root, not an arbitrary current directory.
- Returns inventory as Markdown by default or structured JSON when requested.
- No writes, source-file reads or application execution.
- Nonzero exit and explicit diagnostic on access failure or inventory limit.
- Empty recognized source set means heuristic greenfield/tooling-only, not proof
  the repository contains no code in any language.

`stage start codebase-analysis`:
- Standard order/pending-gate/park checks happen first.
- If condition is false, audit and persist skipped state; no dispatch is needed.
- If condition is true, use existing in-progress behavior.
- No new general-purpose skip command or human gate override is introduced.
