import asyncio

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
