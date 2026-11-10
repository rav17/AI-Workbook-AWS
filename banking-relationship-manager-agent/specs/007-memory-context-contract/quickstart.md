# Quickstart: Memory Context Contract Normalization

## Prerequisites

- Python 3.11 project environment with development dependencies installed.
- Repository root as the current directory.

## Focused Validation

Run the context and adapter tests:

```powershell
.\.venv311\Scripts\python.exe -m pytest tests\framework\test_context_builder.py tests\framework\test_agentcore_adapters.py -q
```

Expected: local and remote-backed retrieval produce the same context entry shape; malformed and cross-tenant provider records fail; absent memory returns the fallback; a missing remote delete method does not delete local records.

Run static checks:

```powershell
.\.venv311\Scripts\python.exe -m mypy aria\framework aria\agent.py
.\.venv311\Scripts\python.exe -m ruff check aria\framework
```

Expected: no new typing or lint errors in the changed framework files.

## Validation Results (2026-10-02)

- Focused context and adapter tests: 25 passed.
- Full Python test suite: 175 passed, with one upstream Pydantic deprecation warning from the installed Bedrock SDK.
- Strict mypy: passed for `aria/framework` and `aria/agent.py`.
- Ruff: passed for all changed source and test files.
- Graphify: refreshed successfully; 1,812 nodes and 2,864 edges. Community labels changed and were not regenerated.