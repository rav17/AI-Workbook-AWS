# Readiness Contract

Existing commands:

```text
python -m speckit_flow sensors run deploy --actor agent:pipeline-deploy
python -m speckit_flow sensors run operate --actor agent:operations
python -m speckit_flow gate approve deploy --actor human:<reviewer>
```

`release-ready` includes required profile-scoped `operational-readiness` builtin
sensor at deploy and operate. Other profiles are unaffected when the pack is
enabled. Disabled pack adds no profile/sensor/stage.

The builtin requires exactly one of each documented level-two section, at least
one substantive non-evidence body line and one non-empty `- Evidence:` line.
Case-insensitive heading match; no prefix match. Comment/fenced code text does
not count. Reject unchecked Markdown tasks, TODO/TBD, NEEDS CLARIFICATION,
ACTION REQUIRED, `{{...}}` and standalone bracket placeholders.

Failures identify filename/section or access issue without copying document
contents into results/audit. Referenced commands/links are not executed or read.
Not-applicable cases need an explanation and human reviewer in the section;
the sensor validates structure, the human judges the explanation.

Passing results bind to current local records and existing spec/plan/tasks.
Editing/removing records after a pass blocks gate approval until sensors rerun.
Structural passing is not a deployment authorization or live readiness proof.
