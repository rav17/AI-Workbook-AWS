import asyncio

from aria.framework.config import FrameworkConfig
from aria.framework.runner import FrameworkRunner


def test_framework_runner_supports_sync_and_async_modes():
    runner = FrameworkRunner()

    sync_result = runner.run(
        {"name": "Aisha", "state_patch": {"segment": "premier"}}, {"risk_appetite": "moderate"}
    )
    async_result = asyncio.run(runner.run_async({"name": "Aisha"}, {"risk_appetite": "moderate"}))

    assert sync_result["status"] == "processed"
    assert sync_result["state"]["segment"] == "premier"
    assert async_result["mode"] == "async"


def test_framework_runner_cleanup_runs_in_finally_block():
    events = []

    def cleanup():
        events.append("cleaned")

    runner = FrameworkRunner()
    result = runner.run({"name": "Aisha"}, cleanup=cleanup)

    assert result["status"] == "processed"
    assert events == ["cleaned"]


def test_framework_runner_enforces_turn_and_tool_limits():
    runner = FrameworkRunner(
        config=FrameworkConfig(max_turns=1, max_tool_calls=1, max_context_tokens=10)
    )

    result = runner.run(
        {
            "name": "Aisha",
            "turn_count": 1,
            "tool_calls": ["crm", "risk"],
            "context": "x" * 100,
        }
    )

    assert result["status"] == "limit_exceeded"
    assert result["reason"] == "max_tool_calls"
    assert len(result["context"]) <= 40


def test_framework_runner_handles_cancellation_and_guardrail_stop_reason():
    runner = FrameworkRunner()

    cancelled = runner.run({"cancelled": True})
    blocked = runner.run({"guardrail_stop_reason": "prompt_injection_detected"})

    assert cancelled == {"status": "cancelled", "reason": "cancelled"}
    assert blocked == {
        "status": "blocked",
        "reason": "prompt_injection_detected",
    }
