from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from strands import Agent
from strands.models import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

from aria.agents.aria.receivables.agent import build_receivables_exception_tool
from aria.agents.aria.receivables.trusted_context import synthetic_harness_context


class ScriptedModel(Model):
    """Model-free SDK seam; any invocation is counted and yields no remote events."""

    def __init__(self) -> None:
        self.calls = 0

    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {}

    async def structured_output(
        self,
        output_model: type[Any],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if False:
            yield {}

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        self.calls += 1
        if False:
            yield {}


class Investigator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def investigate(self, context, payment_id: str, **kwargs: Any) -> dict[str, str]:
        self.calls.append(payment_id)
        return {"payment_id": payment_id}


def test_real_agent_as_tool_exposes_only_input_and_no_session_manager_or_model_calls() -> None:
    scripted = ScriptedModel()
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="s", correlation_id="c"
    )
    child_tool = build_receivables_exception_tool(
        model=scripted, investigator=Investigator(), context=context
    )
    spec = child_tool.tool_spec
    assert set(spec["inputSchema"]["json"]["properties"]) == {"input"}
    assert spec["inputSchema"]["json"]["required"] == ["input"]
    assert child_tool._preserve_context is False
    assert child_tool.agent._session_manager is None
    assert scripted.calls == 0
    assert isinstance(child_tool.agent, Agent)


def test_sdk_rejects_context_preservation_without_model_session_state() -> None:
    scripted = ScriptedModel()
    child = Agent(model=scripted, tools=[])
    wrapped = child.as_tool(name="receivables_test", preserve_context=False)
    assert wrapped.tool_spec["inputSchema"]["json"]["required"] == ["input"]
    assert wrapped.agent._session_manager is None
    assert scripted.calls == 0


def test_real_agent_as_tool_wrapper_invokes_scripted_model_without_network() -> None:
    scripted = ScriptedModel()
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="wrapper", correlation_id="wrapper"
    )
    investigator = Investigator()
    child_tool = build_receivables_exception_tool(
        model=scripted, investigator=investigator, context=context
    )

    async def invoke() -> list[object]:
        events = []
        async for event in child_tool.stream(
            {
                "toolUseId": "receivables-wrapper-invocation",
                "name": "receivables_exception_investigator",
                "input": "Investigate payment exception EXC-SYN-A02",
            },
            {},
        ):
            events.append(event)
        return events

    events = asyncio.run(invoke())
    assert events
    assert scripted.calls == 1
    assert investigator.calls == []


def test_delayed_and_repeated_sdk_invocations_get_independent_budgets() -> None:
    class Clock:
        value = 0.0

        def monotonic(self) -> float:
            return self.value

    clock = Clock()
    model = ScriptedModel()
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="repeat", correlation_id="repeat"
    )
    child_tool = build_receivables_exception_tool(
        model=model, investigator=Investigator(), context=context, clock=clock
    )

    async def invoke() -> None:
        async for _ in child_tool.stream(
            {
                "toolUseId": "repeat",
                "name": "receivables_exception_investigator",
                "input": "Investigate EXC-SYN-A02",
            },
            {},
        ):
            pass

    for invocation in range(6):
        clock.value += 60.0  # Includes idle time before the very first invocation.
        asyncio.run(invoke())
        assert model.calls == invocation + 1
        assert child_tool.agent.model.budget.started == clock.value
        assert child_tool.agent.model.budget.iterations == 1
        assert child_tool.agent.model.budget.deadline == clock.value + 30.0


def test_real_status_tool_bounds_serialized_basemodel_dict_and_scalar_without_model_calls() -> None:
    import json

    from pydantic import BaseModel

    from aria.agents.aria.receivables.agent import MAX_TOOL_OUTPUT_CHARS

    class Status(BaseModel):
        detail: str

    ctx = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="bounded-status", correlation_id="c"
    )
    # Quotes expand in JSON; bounding only the raw value/string would miss this case.
    oversized = '"' * (MAX_TOOL_OUTPUT_CHARS // 2 + 1)
    results = [Status(detail=oversized), {"detail": oversized}, oversized, Status(detail="ready")]
    scripted = ScriptedModel()
    child = build_receivables_exception_tool(
        model=scripted,
        investigator=Investigator(),
        context=ctx,
        status_reader=lambda context, exception_id: results.pop(0),
    )
    status = child.agent.tool_registry.registry["get_proposal_status"]
    for _ in range(3):
        result = status("EXC-SYN-A02")
        assert result["status"] == "error"
        assert len(json.dumps(result)) <= MAX_TOOL_OUTPUT_CHARS
    assert status("EXC-SYN-A02") == {"detail": "ready"}
    assert scripted.calls == 0
