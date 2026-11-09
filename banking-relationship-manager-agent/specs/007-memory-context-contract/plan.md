# Implementation Plan: Memory Context Contract Normalization

**Branch**: `007-memory-context-contract` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Follow-up to the Python design audit findings.

## Summary

Normalize remote AgentCore Memory result dictionaries to the existing `MemoryEntry` type at the adapter boundary. Make context assembly consume a typed retrieval protocol, allow an explicitly absent backend, and ensure a configured remote client's deletion failure cannot fall through to local storage.

## Technical Context

**Language/Version**: Python 3.11 minimum

**Primary Dependencies**: Existing standard library typing/dataclasses and pytest; no new runtime dependencies

**Storage**: Existing local `MemoryStore` and AgentCore Memory data-plane client; no schema or persistence changes

**Testing**: Focused pytest tests, strict mypy, and Ruff

**Target Platform**: Existing Python service and AgentCore Runtime

**Project Type**: Python agent service

**Performance Goals**: Preserve current bounded retrieval limit; normalization is linear in at most the configured number of retrieved entries

**Constraints**: Preserve tenant isolation, current workflow-state precedence, sensitive-text redaction, and the existing deny-by-default Memory write policy

**Scale/Scope**: Internal framework boundary only; no API, database, AWS permission, or dispatcher changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **PASS**: `MemoryEntry` is the existing typed in-process model; no parallel memory representation is introduced.
- **PASS**: Tenant identity is validated before provider results enter context.
- **PASS**: Current workflow state remains authoritative over memory.
- **PASS**: Missing or unsupported remote capabilities fail visibly rather than silently switching stores.
- **PASS**: Deterministic tests cover the adapter and context boundary.

## Project Structure

### Documentation (this feature)

```text
specs/007-memory-context-contract/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
```text
aria/framework/contracts.py
aria/framework/context.py
aria/framework/agentcore.py
aria/framework/memory.py
tests/framework/test_context_builder.py
tests/framework/test_agentcore_adapters.py
```

**Structure Decision**: Keep the normalized consumer protocol in the existing framework contracts module, convert provider records in the existing AgentCore adapter, and test the local/remote composition in the current framework test modules. No new runtime module is warranted.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
No constitution deviations are needed.
