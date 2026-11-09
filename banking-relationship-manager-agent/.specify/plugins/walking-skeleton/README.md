# Walking skeleton (opt-in)

Disabled by default. A human enables `plugin.json`, restarts CLI/session and
validates plugins/doctor, then selects `skeleton-first` via profile workflow.
This adds a developer-led stage after tasks/analyze and before implement, with
quality support and a human gate. Default profiles/stages remain unchanged.

Follow `speckit-skeleton`. Write feature-local `skeleton.md` using the template,
implement one small real input-to-output journey and an executable acceptance
test. Define reserved unit `walking-skeleton` linked to actual feature task IDs,
with `units add ... --files <root-relative-source,test,report,...>`. Include all
files needed to interpret/reproduce the slice, not just an arbitrary three.

The required profile-scoped `skeleton` builtin checks at least three tracked
files, feature-local report inclusion, actual task references and a current
passing unit checkpoint using the receiving project's default `.specify/verify.json`.
A human must approve the project's proposed command before the checkpoint runs.
No verification approval is supplied by the plugin/installer.

Tracked units snapshot files before/after verification. Max 100 unique paths,
each <=1 MiB. Paths must be canonical/root-relative; Windows separators normalize
to `/` in metadata. Traversal, drive paths, aliases, symlinks/reparse ancestors,
non-regular/missing files and access failures are rejected. Only hashes go into
checkpoint records, never source contents.

Rechecks invalidate older tracked-unit success before attempting validation.
Failure, timeout, unapproved command, file/definition edits during verification
or changed command cannot reuse an old pass. Files/definition/command changes
after a pass require a new checkpoint. Adding later units preserves existing
checkpoints. Legacy units without `--files` retain existing checkpoint behavior.

Run stage sensors after checkpointing and stop for human scope/evidence review.
Sensor freshness covers lifecycle artifacts, units metadata, verification policy
and tracked files. Sensors and gates do not execute commands. The builtin always
uses the default receiving-project verify file, not a custom unit CLI override.

**Limitations**: A passing command and file count do not prove architectural or
end-to-end coverage. Humans review actual input/output, boundaries, source/test
roles, mocks and limitations. Only declared files are source-bound; include
fixtures/dependencies/config as needed. Later full implementation may intentionally
change the slice; recheckpoint when relying on it again. No deployment/live
services, source-project domain rules or application generator are included.
