# Quickstart: AI-DLC Agent Roster

1. Validate the roster: `python -m speckit_flow agents validate` → "roster valid: 11 domain, 2 reviewer, 1 composer, 1 conductor".
2. List agents: `python -m speckit_flow agents list`.
3. Show assignments: `python -m speckit_flow agents assign --profile feature` → every stage has one lead.
4. Attribute work: `python -m speckit_flow stage start plan --actor agent:architect` succeeds; `--actor agent:nobody` fails.
5. Human-only decisions: `python -m speckit_flow gate approve specify --actor agent:architect` fails and is audited.
6. Hook: `echo '{"toolName":"bash","toolArgs":{"command":"python -m speckit_flow gate approve plan"}}' | python scripts/speckit_guard.py` → deny; a `status` command → allow.
7. In Copilot Chat, select `speckit-conductor` and ask it to run the plan stage; it dispatches the plan lead and supporters as sub-agents.
8. Run `pytest tests/unit/speckit_flow`, `ruff check`, `mypy speckit_flow`.
