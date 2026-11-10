# Research: Profile-Aware Workflow Orchestration

## One host-driven entry point

Decision: use the installed Specify engine's prompt step to invoke
`speckit-workflow`; do not attempt to dispatch an agent from a shell command.
Evidence: installed `specify_cli/workflows/steps/prompt/__init__.py`
implements arbitrary prompts with a failed result if CLI dispatch is unavailable.
The existing static workflow hard-codes four commands and two gates.
Alternative: expand that YAML with every core/plugin profile. Rejected because
custom routes and project overrides would drift.

## Preserve core compatibility

Decision: retain `init`, `workflow begin`, `profiles suggest` and route storage.
New recommendation/preflight commands are read-only. Existing initialized work
does not get a newly inferred profile.
Evidence: `state.py` enforces stage ordering, park/gates, route and audit state;
`agents.py` already resolves profile overrides and supporting roles.

## Explicit subagent execution boundary

Decision: conductor uses the host agent tool; a matching delegated-stage marker
prevents skill recursion. Validate model invocation and conductor allowlist.
Read-only specialists return text; only the assigned lead owns final artifacts.
Evidence: current design/compliance/reviewer definitions omit edit; the old
conductor incorrectly required every support to write a contribution file.

Strict gated stages need a reviewer even when the roster has none supporting
that stage (notably enterprise clarify/tasks). Preflight supplies the core
product reviewer for early product stages or architecture reviewer otherwise,
without changing project-owned roster/profile files.

## User policy

Confirmed: full-lifecycle recommendation for new features, bugfix for hotfixes,
confirmation before initializing any recommended route. Ambiguity asks the user.
Alternative: change the global legacy default. Rejected because it would break
existing explicit/static clients and migrate existing work unexpectedly.

## Evidence limits

The Python environment running project tests cannot import `specify_cli`, but the
installed Specify CLI has a separate environment. Test its prompt step with a
stubbed integration dispatch there, without launching a second paid CLI session.
Use an explicitly read-only live host smoke test for real subagent invocation.
Neither establishes successful production deployment or every LLM stage outcome.
