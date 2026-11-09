---
name: speckit-skeleton
description: "Build and verify a walking skeleton before full implementation. Use for minimal end-to-end thin slices, source-bound construction checkpoints and the optional skeleton-first route."
---

# Walking-Skeleton Checkpoint

1. Read the selected feature's status, spec, plan, tasks and receiving-project
   constitution/verification policy. Use only its domain and test commands.
2. In profile `skeleton-first`, the developer leads `walking-skeleton` after
   tasks and before full implementation, supported by quality. Define one
   minimal journey with exact input/observable output across the planned
   entry, application and output/storage boundaries. Ask the human when scope
   or access is uncertain; do not silently substitute a unit-only proof.
3. Create feature-local `skeleton.md` using the plugin template only if absent.
   Record scope/task/requirement IDs, exact acceptance assertions, boundary
   diagram/sequence, source and test paths, mocks and limitations. Preserve
   existing work; never fabricate verification or approval evidence.
4. Implement only that slice plus an executable acceptance test through its
   real entry point. Stubs/mocks require explicit labels and human review.
   No production deployment or live-service access is implied.
5. Define reserved unit `walking-skeleton` with actual task IDs and tracked
   root-relative files:
   `python -m speckit_flow units add walking-skeleton "Thin journey" --tasks T001,T002 --files <source>,<test>,<feature>/skeleton.md --actor agent:developer`.
   Include relevant entry, logic, tests, fixtures, configuration and dependencies.
   At least three files and the report are required, but a count proves no
   coverage. Limits: 100 unique regular non-symlink files, 1 MiB per file.
6. Propose the project's actual check using `verify propose --actor agent:developer -- <argv>`.
   Stop for human approval. Never approve on the human's behalf or use the
   toolkit source project's command. The profile uses `.specify/verify.json`;
   hidden custom verify-path overrides do not satisfy its sensor.
7. Finalize the journey report before checkpointing (its content is tracked).
   Run `units checkpoint walking-skeleton --actor agent:developer`. Only report
   actual returned results; source/test/report or command changes require a
   fresh checkpoint. Failed rechecks invalidate previous success. Do not edit
   generated unit/checkpoint metadata directly.
8. Run `sensors run walking-skeleton --actor agent:quality`, return exact
   input/output assertions, checkpoint/sensor results, report and limitations
   to the conductor. Stop for human gate review. If the report is edited to
   add results, recheckpoint it before asking for approval.
9. After the human gate approves, start full implementation and add remaining
   units. Existing checkpoints are preserved on unit addition. Only declared
   files were verified; later edits can invalidate the thin-slice evidence.
   Do not claim this checkpoint proves all architecture, all requirements,
   production readiness or real external integrations.

Manual use outside the profile does not opt a feature into required checks or
approve lifecycle transitions. All real gates and verification approvals remain
human decisions.
