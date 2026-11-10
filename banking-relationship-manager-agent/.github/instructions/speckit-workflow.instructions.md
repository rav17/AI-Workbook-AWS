---
applyTo: "**"
---

# Spec Kit Workflow

- For any code-change request, use `/speckit-workflow` to classify and confirm a profile before initialization. Clear new features recommend `full-lifecycle`; bugs/hotfixes `bugfix`; security fixes `security-patch`; use existing specialized profiles for refactors, infrastructure and experiments. Ask if intent is ambiguous/mixed. Explicit profile selection wins but still needs confirmation.
- Distinguish new work from resuming the active feature; ask when unclear. Preserve initialized routes unless explicitly switched at a stage boundary.
- Use `python -m speckit_flow workflow dispatch` preflight and invoke `speckit-conductor` through the host subagent tool. Assigned stage leads execute matching skills with a conductor-supplied delegated-stage marker; direct stage skill calls hand off once, not recursively.
- Do not silently replace unavailable subagent execution with parent-only work. Report the blocker. Follow only the confirmed route and stop at human gates; a completed workflow session is not a completed feature or deployment authorization.
- Check `.specify/memory/constitution.md` if the receiving project has one. Never assume another repository's domain rules apply.
- Use the receiving project's language, build and test commands. Propose its verification command and require human approval before using it for construction checkpoints.
- Treat `.specify/custom/`, plugins, profiles, agents, sensors, rules and knowledge as project-owned configuration; do not overwrite local settings during workflow updates.
- Optional domain packs are opt-in. Confirm their guidance, gates, sensors and agent dispatch configuration before enabling them.
- Do not approve human gates, learned rules or verification commands on behalf of the user.
