# Team knowledge

Put team standards here as short markdown files. Each file may start with:

```text
title: Human readable title
stages: plan, implement      # or "all" (default)
```

`python -m speckit_flow knowledge list --stage plan` returns titles and paths only.
Agents open a document only when it is relevant. Never store secrets or customer data here.
