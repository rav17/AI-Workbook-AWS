# Implementation Plan: Intents and Session Control

**Branch**: `014-intents-session-control` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

## Summary

Add `speckit_flow/session.py` (list/switch intents, park/unpark, redo/jump) and `scripts/speckit_session.py` (sessionStart hook). Parked status is derived from the audit trail via `audit.is_parked`; `state.start_stage` refuses parked features. New CLI: `intents list|switch|park|unpark`, `redo`, `jump`. New event types `intent_switched`, `intent_parked`, `intent_resumed`, `stage_redone`.

## Technical Context

Python 3.11 stdlib only. Storage: existing `.specify/feature.json` pointer, audit trail; no new state files. Tests: pytest. Constraint: backward compatible; no change to state.json schema.

## Constitution Check

All principles PASS: no new authority (redo is human-only), state remains structured, audit remains append-only, session context lives in files not conversation.

## Structure

```text
specs/014-intents-session-control/  spec.md plan.md research.md data-model.md quickstart.md tasks.md contracts/cli.md
speckit_flow/session.py  (+ audit.py is_parked, models.py events, state.py start_stage check, cli.py)
scripts/speckit_session.py  .github/hooks/speckit-session.json
tests/unit/speckit_flow/test_flow_session.py
```
