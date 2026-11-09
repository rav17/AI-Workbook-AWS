# Data Model

Unit optional `files`: non-empty unique root-relative canonical path list,
maximum 100 files, each regular file at most 1 MiB. Empty/missing field means
legacy unit behavior. Checkpoints for tracked units include `files` (path/hash
map) and `definition` (hash of unit identity/title/deps/tasks/files), plus existing
timestamp, actor and approved command digest.

Skeleton unit ID: `walking-skeleton`. Requires nonempty task IDs present in
feature tasks.md, >=3 tracked files and feature-local `skeleton.md` among them.
Report describes actual implementation/test roles; counts do not prove coverage.

Tracked checkpoint: invalidate old success -> snapshot -> approved verification
-> compare current snapshot/definition/command -> persist pass or return failure.
No evidence on failure, even after an earlier pass. Later unit additions preserve
existing checkpoint records. Sensor never runs commands and requires current
definition, files and approval digest.
