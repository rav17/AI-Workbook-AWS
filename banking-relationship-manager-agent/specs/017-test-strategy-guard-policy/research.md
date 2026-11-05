# Research: Test Strategy and Guard Policy

- **Decision:** two independent profile fields rather than extending `depth`. `depth` stays about artifact detail.
- **Decision:** unset `guard_policy` falls back to strict for `depth: comprehensive`, so shipped profiles behave exactly as before; an explicit `standard` opts out.
- **Decision:** if the profile cannot be loaded at a gate, approval is refused rather than falling back to depth, so a broken profile cannot silently relax a strict policy.
- **Not built:** per-profile "ceremony" toggles (for example skipping learning prompts). Our learning loop has no prompts, so there is nothing to toggle yet.
