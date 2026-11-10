# Quickstart and Verification Proposal

## Approved verification

The user explicitly approved the plan and the complete verification scope below
before implementation.

```powershell
pytest tests\unit\speckit_flow\test_flow_orchestration.py tests\unit\speckit_flow\test_flow_workflow.py tests\unit\speckit_flow\test_flow_profiles.py tests\unit\speckit_flow\test_flow_agents.py tests\unit\speckit_flow\test_flow_doctor.py tests\unit\test_speckit_bootstrap.py -q
ruff check speckit_flow tests\unit\speckit_flow tests\unit\test_speckit_bootstrap.py
mypy speckit_flow
python -m speckit_flow doctor
python -m speckit_flow agents validate
python -m speckit_flow plugins validate
```

The approval includes a deterministic installed-engine prompt-step test with stubbed
dispatch (no live model call), plus a bounded read-only real conductor/subagent
smoke test. The smoke test must not edit files, approve gates, deploy or claim
the feature is complete. Graphify refresh follows code changes.

## Acceptance scenarios

1. Request a feature: recommend full-lifecycle; ask to confirm before init.
2. Request bug/hotfix/security/refactor/infra/POC: show the expected profile.
3. Give vague or mixed intent: ask; do not silently initialize a default.
4. Enter a direct stage: hand off once; only the delegated matching lead runs
   the skill body. Out-of-order/omitted stages block.
5. Test all core profile assignments, read-only contributions, independent
   reviewers, missing permissions and disabled model invocation.
6. Pending gate, parked feature, audit damage or worker failure: no advancement.
7. Portable install: entry skill/instructions/engine are included; local
   settings and disabled pack defaults remain intact.

Standard engine execution is a host session, not a claim that the lifecycle
finished. Re-enter after real human decisions; inspect lifecycle status/resume.

## Installed engine and host invocation evidence

- Installed Specify engine prompt success and missing-dispatch failure tests,
  plus workflow definition validation: **3 passed** using the installed CLI's
  environment on the test import path. The default project interpreter reports
  these as optional skips; they were explicitly exercised separately.
- A real `speckit-conductor` invocation used the actual host agent tool to call
  `speckit-design`, `speckit-developer`, and `speckit-architecture-reviewer`
  separately. Each returned its own role and the expected smoke-test nonce.
- This was a bounded read-only invocation test. It made no stage transitions,
  wrote no artifacts, ran no stage skills and approved nothing.
- It verifies nested host invocation for these representative roles, not every
  agent's generated outputs or a live full-lifecycle project.

## Final validation results

- Approved focused workflow/profile/agent/doctor/portability suite:
  **121 passed, 3 skipped**. All three optional engine checks passed separately
  in the installed engine environment as recorded above.
- After adding the strict-gate reviewer fallback, final orchestration/agent
  regression rerun with `python -m pytest`: **44 passed, 2 skipped**.
  These tests overlap the larger suite; do not add their counts together.
  The earlier launcher rerun stalled after reaching 100% and was stopped;
  the interpreter-based retry completed normally.
- Ruff: **all checks passed**.
- Mypy: **no issues in 25 source files**.
- Doctor, agent validation and plugin validation: **passed**; all 6 optional
  plugins remain disabled.
- `graphify update .`: **completed after final code changes**.
- Feature-scoped whitespace/diff inspection: completed; unrelated edits,
  including the existing plugin-loader change, were preserved.

The static workflow entry now invokes a host session, and direct core stage
skills have recursion-safe handoffs. Actual full-lifecycle feature generation,
all 14 specialist outcomes and deployment remain outside this smoke-test evidence.
Start a new Copilot session if newly added skills or refreshed agent definitions
are not discovered in an already running session.
