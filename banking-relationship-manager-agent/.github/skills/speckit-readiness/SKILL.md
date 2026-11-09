---
name: speckit-readiness
description: "Prepare evidence-backed operational readiness, release checks and runbooks. Use for deploy/operate handoffs in the optional release-ready profile."
---

# Operational Readiness

1. Read the selected feature's status/profile, spec, plan, tasks and the receiving
   project's constitution and verification policy. Do not copy domain policies
   or verification commands from the toolkit's source project.
2. For profile `release-ready`, pipeline-deploy owns the release record and
   operations owns the runbook/handoff. Use existing agent assignments. Copy
   templates from `.specify/plugins/operational-readiness/templates/` into the
   feature as `release.md` and `runbook.md` only when absent; preserve existing
   content. Prepare both before the deploy gate.
3. Replace all placeholders with feature/revision-specific procedures:
   - Release: Ownership and target, Configuration, Verification, Rollout, Rollback.
   - Runbook: Ownership, Health signals, Alerts, Incidents, Rollback, Feedback.
   Keep exact level-two headings and at least one substantive body line plus
   `- Evidence: ...` per section. Do not hide evidence in comments/code blocks.
4. Connect evidence to requirement/design/task IDs, reviewed procedures and
   actual approved test/checkpoint records. Distinguish planned, executed,
   failed and untested work. Reference monitoring queries, thresholds, routing,
   escalation roles, recovery/data-compatibility checks and feedback ownership.
   Do not fabricate outcomes or treat a document as proof a live check ran.
5. If an area is not applicable, keep its section, explain why and identify a
   human reviewer and review reference in Evidence. Do not self-approve risk
   exceptions. Ask the human if evidence is unavailable. Keep secrets,
   personal/customer data and raw operational logs out of artifacts.
6. Run `python -m speckit_flow sensors run <deploy|operate> --actor agent:<role>`.
   Surface errors and incomplete areas. Readiness checks only local document
   structure and freshness, not the truth of evidence or live system health.
   They execute no evidence links/commands and authorize no deployment.
7. Operations revisits both records at operate and records actual handoff state
   and planned feedback collection, not invented operational history. Recheck
   affected evidence after edits and rerun sensors before presenting the gate.
   External evidence is not fingerprinted: use immutable/versioned references
   and request human revalidation when it changes.
8. Return artifacts, check results, unresolved risks and the pending gate to the
   conductor. Stop for human evidence review and gate approval. Never approve
   gates/verification commands, deploy, roll back, or run live health probes.
   This skill prepares procedures, not application/infrastructure changes.

Other profiles are unchanged. Manual use can prepare records but does not
silently opt a feature into required checks or approve lifecycle transitions.
