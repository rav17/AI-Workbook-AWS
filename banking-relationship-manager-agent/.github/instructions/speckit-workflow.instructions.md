---
applyTo: "**"
---

# Spec Kit Workflow

- For any code-change request, use `/speckit-workflow` to classify and confirm a profile before initialization. Recommend delegated `feature` for ordinary features and `bugfix` for ordinary fixes; `quick` is an explicit opt-in inline alternative. Use risk-appropriate profiles such as `security-patch` or `enterprise` for consequential work. Assess real risk, not just keywords; ask when uncertain or mixed. Explicit profile selection still needs confirmation.
- Distinguish new work from resuming the active feature; ask when unclear. Preserve initialized routes unless explicitly switched at a stage boundary.
- Use `python -m speckit_flow workflow dispatch` preflight. Run an `inline` stage in the host with its inline marker. For a `delegated` stage, an already active `speckit-conductor` coordinates directly; another host invokes it once only with named-conductor and nested-worker support. With nesting disabled, select the conductor top-level. Never recursively re-enter workflow/conductor. Direct stage commands hand off once; assigned workers execute the matching stage body, or stop on a bad/missing marker instead of handing back.
- For standalone read-only reviews, do not start a lifecycle merely to review; handle small reviews directly unless independent lifecycle evidence is required. For delegated stages use only assigned agents and the conductor's bounded review limit.
- Do not silently replace required delegation with parent-only work. Report the blocker. Follow only the confirmed route and stop at human gates; a completed workflow session is not a completed feature or deployment authorization.
- Check `.specify/memory/constitution.md` if the receiving project has one. Never assume another repository's domain rules apply.
- Use the receiving project's language, build and test commands. Propose its verification command and require human approval before using it for construction checkpoints.
- Treat `.specify/custom/`, plugins, profiles, agents, sensors, rules and knowledge as project-owned configuration; do not overwrite local settings during workflow updates.
- Optional domain packs are opt-in. Confirm their guidance, gates, sensors and agent dispatch configuration before enabling them.
- Do not approve human gates, learned rules or verification commands on behalf of the user.
- Before every approval request, present a readable review package in chat: decision/scope, work and change summary, direct artifact links, actual test/review/sensor evidence, unresolved findings/limitations, and what approval authorizes next and excludes. Links only in a form or a subagent status report are insufficient. Follow `.github/skills/speckit-workflow/SKILL.md`, section 4; show the plan before plan approval and the task breakdown before implementation, even without a separate tasks gate. Do not treat missing/stale evidence, empty sensors, or silence as approval or verification.
