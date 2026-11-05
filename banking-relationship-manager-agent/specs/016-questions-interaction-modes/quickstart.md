# Quickstart: Questions File

1. `python -m speckit_flow questions add "Which users?" --role product --actor agent:product`
2. `python -m speckit_flow questions check` exits 1 and lists `Q1 [product]`.
3. Answer with `questions answer Q1 "Branch staff" --actor human:you`, or type after `**Answer:**` in `questions.md`.
4. `questions check` now exits 0; `sensors run plan` passes `no-open-questions`.
5. Run `python -m pytest tests/unit/speckit_flow/test_flow_policy_questions.py tests/unit/speckit_flow/test_flow_cli_015_017.py -q`.
