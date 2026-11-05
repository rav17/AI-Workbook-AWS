# Research: Compliance Plugin Pack

## R1: How should the compliance check be expressed?

- **Finding**: Sensors are `builtin` (consistency, traceability, questions) or `command`. A command sensor runs with the repo root as its working directory and is given no feature directory, so it cannot find the artifact to check.
- **Decision**: Add a `section` built-in sensor with options `heading` and optional `artifact` (default: the stage's main artifact).
- **Rationale**: Deterministic, no subprocess, reusable by any team (for example "Rollback plan"). Matches the constitution's rule that enforcement lives in code.
- **Alternatives**: A command sensor with a script (rejected: no feature context, would need a new env contract); a prompt instruction to the agent (rejected: not enforceable).

## R2: How can the sensor apply to the compliance profile only (FR-004)?

- **Finding**: `for_stage` selects by stage only; there is no profile scope, so a plugin sensor on `plan` would block every profile.
- **Decision**: Add an optional `profiles` list to a sensor. If present, the sensor applies only to features whose state profile is listed. Absent means all profiles (unchanged behaviour).
- **Rationale**: Backward compatible; needed for any plugin that adds enforcement.
- **Alternatives**: Put the sensor in the profile file (rejected: profiles do not own sensors today); make the pack's sensor global (rejected: breaks FR-004 and SC-002).

## R3: Can the pack's agent be a plain extra agent?

- **Finding**: Feature 024 allows plugin `agents.json` entries that are `domain` agents which only support stages. `validate_roster` checks the agent file frontmatter, and the conductor `agents` list must include every core agent and may include extras.
- **Decision**: Add `compliance-reviewer` (read-only, supports specify and plan). Its agent file lives in `.github/agents/`, and the conductor lists it.
- **Rationale**: Uses the shipped route; no new mechanism.
- **Catch**: The agent file exists even when the pack is disabled. Doctor only checks files of loaded agents, so a disabled pack is harmless, and the conductor may list an agent that is not in the roster only if the roster check allows it. See R4.

## R4: Conductor lists an extra agent while the pack is disabled

- **Finding**: Current rule is `core <= listed <= everyone`. A listed agent that is not loaded breaks it.
- **Decision**: Do not list the pack agent in the conductor file. The conductor reads the roster at run time; document that teams add extras to `agents` when they enable a pack.
- **Rationale**: Keeps the disabled state valid (FR-006, SC-004).
- **Alternatives**: Relax the rule (rejected: weakens an existing check).

## R5: Disabled by default

- **Decision**: `plugin.json` has `enabled: false`. Tests copy the pack into a temp project and enable it there.
