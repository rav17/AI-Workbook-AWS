---
applyTo: "**"
---

# Spec Kit Workflow

- For code changes, use the installed `/speckit-*` workflow: specify, plan, tasks, then implement.
- Check `.specify/memory/constitution.md` if the receiving project has one. Never assume another repository's domain rules apply.
- Use the receiving project's language, build and test commands. Propose its verification command and require human approval before using it for construction checkpoints.
- Treat `.specify/custom/`, plugins, profiles, agents, sensors, rules and knowledge as project-owned configuration; do not overwrite local settings during workflow updates.
- Optional domain packs are opt-in. Confirm their guidance, gates, sensors and agent dispatch configuration before enabling them.
- Do not approve human gates, learned rules or verification commands on behalf of the user.
