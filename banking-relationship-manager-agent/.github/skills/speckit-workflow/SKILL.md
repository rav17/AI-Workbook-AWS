---
name: speckit-workflow
description: "Route new features, bugfixes, hotfixes, refactors and infrastructure requests to a confirmed Spec Kit profile; orchestrate lifecycle stages through the conductor. Use for code-change requests, standard workflow entry, direct stage handoffs and resuming work."
---

# Profile-Aware Lifecycle Entry

Run from the receiving Spec Kit project root. Activate the Copilot integration
before invoking Spec Kit skills. Read its constitution when present.
No application/domain policy from the toolkit source is implied.

## 1. Identify the work and confirm the route

- Distinguish a new work item from explicitly resuming the active feature.
  If that distinction is unclear, ask the user; do not attach a new request to
  whichever feature pointer happens to be active.
- For an explicitly resumed initialized feature, run `python -m speckit_flow resume`
  and preserve its profile. Do not initialize again, infer a replacement route,
  reset completed work or switch without explicit user confirmation.
- For a new work item, run
  `python -m speckit_flow workflow recommend "<request>" --json`.
  If the user named a profile, pass `--profile <id>`. This read-only heuristic
  returns advice, not a decision. Consider the actual intent, not just keywords.
- Clear new feature: recommend `full-lifecycle`. Bug/hotfix: `bugfix`;
  security fix: `security-patch`; refactor: `refactor`; infrastructure: `infra`;
  experiment: `poc`; high-assurance delivery: `enterprise`.
- Present stages, gates and the reason. **Always ask the user to confirm the
  profile before initialization**, even for an explicit name. If
  `needs_clarification` is true, ask what kind of work it is / which available
  profile to use. Do not silently use `feature`. Never enable plugins to make
  a requested profile available. Suggest `speckit-compose` for a custom route.

## 2. Establish the feature context

After confirmation, allocate exactly one feature directory using the receiving
project's numbering/template rules from `speckit-specify` (or its explicit user
path). Persist the feature pointer. Do not create a second directory when the
specify stage later runs. Allocation alone is not stage completion.
This bootstrap allows ideation before a spec exists.

Run `python -m speckit_flow init --profile <confirmed-id> --feature-dir <path> --actor agent:conductor`.
If audit exists without state, or initialization fails, stop and report it;
do not overwrite or rebuild automatically.

## 3. Dispatch through the conductor

Run `python -m speckit_flow workflow dispatch --feature-dir <path> --json`.
For an external direct-stage handoff, add `--stage <requested-stage>`.
This validates eligibility only; it does not invoke models.

- If complete, report lifecycle completion without redispatch.
- If blocked (pending human gate, parked feature, damaged audit, omitted or
  out-of-order stage, invalid/unavailable agent), stop and explain the blocker.
- If ready, **invoke the actual `speckit-conductor` custom agent** with a bounded
  brief: request, feature directory, requested stage and preflight output.
  Require it to use the host subagent tool for the assigned specialists.
- If the host cannot invoke the conductor or nested specialists, stop and say
  subagent orchestration is unavailable. Do not silently execute the skill body
  in the parent and call it delegation.
- The conductor's lead brief contains `SPECKIT_DELEGATED_STAGE=<stage>` and
  explicit lead identity. This is a recursion marker, not an authorization
  token. Only that matching stage lead executes the stage skill body.

The conductor returns after one stage. For a full workflow request, repeat
preflight for the next stage only when there is no blocker or pending gate.
For a direct-stage request, return after that one stage; do not continue the route.
Never redispatch a failed or in-progress stage blindly; inspect actual results
and ask whether to resume the interrupted work.

## 4. Human decisions and resume

At a pending gate, show actual artifacts, independent review and sensor results.
Ask the human to approve/reject; record only the decision they actually made.
For a rejected gate, explain `redo` and wait for an explicit human instruction.
Re-run stale sensors/reviews before approval. Agents never supply `human:` actors
without that actual user decision, or approve verification/learned rules.

Use `/speckit-workflow resume` after a human decision or interruption. An engine
workflow run is a **session**, not proof the feature completed; check lifecycle
status. Do not auto-resume an old static four-stage engine cursor under this new
workflow. No deploy/operate profile authorizes commands against live resources.
