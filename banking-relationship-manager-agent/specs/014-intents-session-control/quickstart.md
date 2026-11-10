# Quickstart

1. `python -m speckit_flow intents list` - features with an active marker.
2. `python -m speckit_flow intents park --reason "waiting on legal"` then `stage start ...` is refused; `intents unpark` restores.
3. `python -m speckit_flow redo plan --reason "scope changed" --actor human:me` - plan and later stages return to pending.
4. `python scripts/speckit_session.py` - one-line context.
5. `pytest tests/unit/speckit_flow/test_flow_session.py -q`.
