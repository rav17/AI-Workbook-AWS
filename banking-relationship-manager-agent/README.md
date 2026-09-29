# Aria AI Relationship Manager

Aria is a Python 3.11 relationship-management agent with guarded workflow state, CRM and knowledge tools, escalation handling, shared framework contracts, and AWS CDK infrastructure.

## Development setup

Use the repository-local Python 3.11 environment:

```powershell
C:\Python311\python.exe -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv311\Scripts\python.exe -m pip install -r cdk/requirements-dev.txt
```

Run the application tests:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q
```

Run CDK synthesis:

```powershell
cd cdk
cdk synth --quiet
```

The current CDK slice is intentionally local and deterministic. It provisions stateful workflow infrastructure; AgentCore Runtime, Gateway, and Memory integrations remain behind application contracts until their AWS SDK and deployment configuration are approved.

## Project layout

- `aria/`: application, workflow, tools, guards, persistence, and shared framework
- `aria/agents/`: manifest-driven agent entrypoints
- `cdk/`: AWS infrastructure and synthesis tests
- `tests/`: unit and framework tests
- `specs/001-ai-relationship-manager/`: authoritative Spec Kit artifacts
- `docs/`: operational and framework documentation
