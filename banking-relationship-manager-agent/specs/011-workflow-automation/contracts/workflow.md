# Standard Workflow Contract

The workflow retains its existing stages and gates:

| Order | Lifecycle stage | Workflow operation |
|---:|---|---|
| 1 | specify | After the specify command creates the feature directory, workflow preflight initializes state, then records start and completion before the first gate |
| 2 | specify gate | Human choice is recorded by `gate approve` or `gate reject`; rejection stops subsequent execution |
| 3 | plan | Start before `speckit.plan`; complete only after success |
| 4 | plan gate | Human choice is recorded; rejection stops subsequent execution |
| 5 | tasks | Start before `speckit.tasks`; complete only after success |
| 6 | implement | Start before `speckit.implement`; complete only after success |

The workflow preflight declares expected stages `specify,plan,tasks,implement` and gates `specify,plan`. A non-matching profile is not silently rewritten; the standard workflow reports the mismatch and directs the contributor to the `speckit-profile` skill.

Engine gate steps use `on_reject: skip` only so a following conditional can persist `gate_rejected`. The rejection branch then exits non-zero, and the engine must not execute later stages. Approval branches call the lifecycle gate validator before proceeding.
