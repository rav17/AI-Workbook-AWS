# Operational readiness (opt-in)

Disabled by default. This provider-neutral pack connects release decisions and
operational handoff to existing feature state, sensor audit and human gates.
It adds no stages/agents and executes no deployment or live infrastructure checks.

## Enable

A human reviews this pack and changes `plugin.json` to `"enabled": true`.
Restart the session/CLI, run plugins validation and doctor, then select profile
`release-ready` through the profile workflow. Existing profiles are unaffected.
The static default `feature` workflow remains unchanged.

Route: specify -> plan -> tasks -> implement -> deploy -> operate.
Human gates: specify, plan, implement, deploy, operate. Existing pipeline-deploy
and operations agents lead the last two stages. The conductor follows
`speckit-readiness`, prepares records and stops at human gates.

## Records and checks

Copy `templates/release.md` and `templates/runbook.md` into the feature directory
only when absent, replacing all placeholders with actual procedures and evidence.
Keep exact level-two headings. Every required section needs substantive body text
and a standalone `- Evidence: ...` line. Non-applicable cases need an explanation,
reviewer and reference; the human judges that explanation.

The required profile-scoped `operational-readiness` builtin runs at deploy and
operate. It rejects missing/empty sections, template markers, unchecked tasks,
duplicate headings, examples/comments posing as evidence, non-UTF-8 files,
symlinks/reparse points, non-regular files and files over 256 KiB. Diagnostics
identify the record/section without copying contents into sensor audit.

Readiness hashes `release.md`, `runbook.md` and the existing spec/plan/tasks.
Editing/deleting records makes a pass stale; access errors block gate use.
Unrelated sensors keep their existing fingerprint scope. Run sensors again
after changes before requesting a human gate decision.

## Evidence boundaries

A pass means record structure, not verified evidence truth, live health or
authorization to deploy. No linked file/URL/command is read or executed by this
sensor. Linked evidence changes are not automatically detected: prefer immutable
references and human revalidation. Plans and untested procedures must be labeled;
do not manufacture successful tests, rollback exercises or operational outcomes.
No cloud access, application changes or verification approvals are introduced.

## Adapt

The receiving project owns its installed plugin/templates/profile. Review and
change its gates, support assignments and guidance deliberately; maintain the
human gate and evidence boundaries. Copy the sensor's profile scope explicitly
if using a differently named custom profile. New sensor options are not supported;
do not silently assume domain-specific/live checks are included.
