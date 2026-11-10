# Plan: Custom and plugin agents

`speckit_flow/agents.py`: add `Agent.source`, `_extra_sources`, merge in `load_roster`, adjust `validate_roster`. The guard already protects `.specify/custom/` and `.specify/plugins/`.
