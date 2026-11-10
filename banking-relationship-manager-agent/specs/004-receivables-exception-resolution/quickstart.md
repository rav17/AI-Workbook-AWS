# Quickstart: Receivables Exception Resolution (synthetic MVP)

**None of the commands below have been run or approved.** They are proposals for the plan gate. Construction, verification and measurement require separate human approval. No live AWS, network, real model, real data, commit, or deploy is involved.

## Prerequisites
- Windows PowerShell; working directory `C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent`.
- Local interpreter `.\.venv311\Scripts\python.exe` (exists; not executed here). Ruff and mypy are `.\.venv311\Scripts\ruff.exe` and `.\.venv311\Scripts\mypy.exe` (exist; not executed).
- Human-approved copy of `synthetic-policy.md` values and `synthetic-fixtures.json`, with an approval record before any "approved policy" run. Without it, every case correctly fails closed `POLICY_UNAPPROVED`.
- Q5 resolves the storage boundary: isolated synthetic local test/demo persistence for internal proposals, analyst decisions, confirmation/idempotency bindings and audit is permitted; the create-only mock case task remains the sole business write, with no financial, source-record or production changes. This does not approve the proposed SQLite design or implementation, policy values, fixtures, evaluation labels or commands. Store construction and use still require their respective human approvals; no ephemeral substitute is assumed.

## Proposed commands (future, exact)

New modules (pytest config: `pythonpath=["."]`, `addopts=-ra`):
```powershell
.\.venv311\Scripts\python.exe -m pytest tests/unit/test_receivables_rules.py tests/unit/test_receivables_fixtures.py tests/unit/test_receivables_metrics.py tests/unit/test_receivables_store.py tests/unit/test_receivables_trusted_context.py -q
.\.venv311\Scripts\python.exe -m pytest tests/framework/test_receivables_subagent.py tests/framework/test_receivables_agent_as_tool.py -q
.\.venv311\Scripts\python.exe -m pytest tests/property/test_receivables_properties.py -q
```
Existing regression relevant to untouched boundaries:
```powershell
.\.venv311\Scripts\python.exe -m pytest tests/framework/test_agentcore_entrypoint.py tests/framework/test_kyc_aml_subagent.py tests/framework/test_statement_subagent.py tests/unit/test_statement_gateway_handler.py tests/unit/test_kyc_aml_verification.py -q
```
Static checks, scoped to new paths only (existing-code baseline unverified):
```powershell
.\.venv311\Scripts\python.exe -m ruff check aria/agents/aria/receivables demo/receivables_exception tests/unit/test_receivables_rules.py tests/unit/test_receivables_fixtures.py tests/unit/test_receivables_metrics.py tests/unit/test_receivables_store.py tests/unit/test_receivables_trusted_context.py tests/framework/test_receivables_subagent.py tests/framework/test_receivables_agent_as_tool.py tests/property/test_receivables_properties.py
.\.venv311\Scripts\python.exe -m ruff format --check aria/agents/aria/receivables demo/receivables_exception
.\.venv311\Scripts\python.exe -m mypy aria/agents/aria/receivables demo/receivables_exception
```
Notes: `ruff format` configuration beyond line-length 100 is not in pyproject, so format-check defaults are unverified. `tests/integration` does not exist; this plan uses `tests/unit`, `tests/framework`, `tests/property`.

## Model-free test seams (to build, not built)
Fixed clock `2026-03-16T12:00:00Z`; read-only fixture ports with call recorder; scripted result seam; decision-store interleaving hook; in-memory audit sink for rule tests; proposed SQLite file in `tmp_path` for local transaction/immutability tests after the store design and construction receive human approval; scripted `Model` subclass for the real `as_tool` test. SC-006 instrumentation must cover every implemented planned source and writer surface in both evaluation and workflow/demo paths, report coverage, hash immutable fixture files before/after, and assert DB immutability/create-only task behavior where applicable. Missing or unexercised surfaces are unmeasured, not passing zeros. Fakes prove logic, not atomicity or cloud behavior; no cloud/network path is exercised.

## Walkthrough (once built and approved)
1. Load catalogue; verify counts (57 cases = 52 scored + 5 guards; denominators in `plan.md` section 8) before any run.
2. Run E: investigate all 57 cases without an analyst; compute metrics per `synthetic-policy.md`; report numerators, denominators, disposition counts, unscored count, per-stratum, N/A for zero denominators.
3. Run W: execute the 14 workflow scenarios in `synthetic-fixtures.json` (server-issued identity binding, exact retry/replay, changed-binding conflict, revised approval with a new identity, both race orders, failures, cross-tenant/session, role and TTL).
4. Assert no source port exposes a write-capable method; instrument every planned writer surface, compare immutable fixture hashes, and assert no task UPDATE/DELETE path. Report coverage and limit conclusions to observed implemented paths; absent or unexercised surfaces are not evidence of global zero. Persistence/DB assertions require separate human approval of the plan and store implementation.
5. Report targets as targets; do not claim achievement until the human-approved set is evaluated.
