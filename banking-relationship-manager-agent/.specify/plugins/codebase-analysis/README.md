# Existing-codebase analysis (opt-in)

Disabled by default. Enable `plugin.json`, restart the session/CLI, validate
profiles, then select `brownfield` for the intended feature. No new agents,
automatic domain specialists, sensors or verification commands are enabled.

The optional architect-led stage follows specification and precedes planning.
The conductor collects `python -m speckit_flow codebase scan` and passes it to
the architect, who follows `/speckit-codebase` to write feature-local `codebase.md`.
The scan itself is a path inventory, not semantic analysis or test execution.

Starting the stage automatically skips it with an audited reason when no
recognized source exists. Normal ordering, parking and pending gates still
apply. Conditional stages cannot be required stages or human approval gates.

See [workflow documentation](../../../docs/speckit-profiles.md) for heuristic
limits and exclusions. Projects using unrecognized languages should run the
skill manually and explicitly record the missing inventory coverage.
