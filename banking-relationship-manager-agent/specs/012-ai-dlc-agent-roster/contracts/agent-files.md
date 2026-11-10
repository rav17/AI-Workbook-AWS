# Agent File Contract

Each file `.github/agents/speckit-<id>.agent.md`:

```yaml
---
name: speckit-<id>
description: <one sentence>
user-invocable: false        # conductor: true
tools: [...]                 # minimal scope
---
<persona, stage responsibilities, output expectations, boundaries>
```

| Role | Tools |
|------|-------|
| product, design, compliance | `read`, `search`, `web` |
| architect, delivery | `read`, `search`, `edit` |
| aws-platform, devsecops, developer, quality, pipeline-deploy, operations | `read`, `search`, `edit`, `execute` |
| reviewers | `read`, `search`, `execute` (only to run `speckit_flow review`) |
| composer | `read`, `search`, `execute` (only to run `speckit_flow compose validate`) |
| conductor | `read`, `search`, `execute`, `agent`; `agents:` lists all 14 roster agents |

All agents state: only a human approves gates and rules; read `python -m speckit_flow status` and the stage's assignments before acting; record themselves with `--actor agent:<id>`.
