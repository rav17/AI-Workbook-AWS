from __future__ import annotations

import inspect
import time
from typing import Any

import pytest
from strands.models import Model

from aria.agents.aria.receivables.agent import (
    _BudgetedModel,
    build_receivables_exception_tool,
    should_route_receivables_request,
)
from aria.agents.aria.receivables.trusted_context import synthetic_harness_context


class EmptyModel(Model):
    def __init__(self) -> None:
        self.calls = 0

    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        if False:
            yield {}

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls += 1
        if False:
            yield {}


class CapturingAgent:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.session_manager = kwargs.get("session_manager")

    def as_tool(self, **kwargs: Any) -> CapturingAgent:
        self.as_tool_kwargs = kwargs
        return self


class Investigator:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def investigate(self, context, payment_id: str, **kwargs: Any) -> dict[str, str]:
        self.calls.append((context, payment_id, kwargs))
        return {"status": "synthetic_only"}


def test_scoped_handoff_preserves_trusted_context_and_exposes_only_read_tools(monkeypatch) -> None:
    import aria.agents.aria.receivables.agent as agent_module

    monkeypatch.setattr(agent_module, "Agent", CapturingAgent)
    monkeypatch.setattr(agent_module, "tool", lambda function: function)
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u1", session_id="s1", correlation_id="c1"
    )
    investigator = Investigator()
    tool = build_receivables_exception_tool(
        model=EmptyModel(), investigator=investigator, context=context
    )
    tools = {item.__name__: item for item in tool.kwargs["tools"]}
    assert set(tools) == {"investigate_exception", "get_proposal_status"}
    assert list(inspect.signature(tools["investigate_exception"]).parameters) == ["exception_id"]
    assert list(inspect.signature(tools["get_proposal_status"]).parameters) == ["exception_id"]
    assert "approve" not in repr(tool.kwargs["tools"]).lower()
    assert "confirm" not in repr(tool.kwargs["tools"]).lower()
    assert "tenant_id" not in repr(tool.kwargs["system_prompt"])
    assert tool.as_tool_kwargs["preserve_context"] is False
    assert tool.session_manager is None
    assert tools["investigate_exception"]("EXC-SYN-A02")["status"] == "synthetic_only"
    assert investigator.calls[0][0] == context
    assert investigator.calls[0][1] == "PAY-SYN-A02"
    assert should_route_receivables_request("Investigate this payment exception")
    assert not should_route_receivables_request("What is my portfolio risk profile?")


def test_untrusted_payload_identity_is_not_used_for_handoff(monkeypatch) -> None:
    import aria.agents.aria.receivables.agent as agent_module

    monkeypatch.setattr(agent_module, "Agent", CapturingAgent)
    monkeypatch.setattr(agent_module, "tool", lambda function: function)
    calls: list[str] = []

    class Capture:
        def investigate(self, context, payment_id, **kwargs):
            calls.append(payment_id)
            return {"ok": True}

    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="real-user", session_id="s", correlation_id="c"
    )
    tool = build_receivables_exception_tool(
        model=EmptyModel(), investigator=Capture(), context=context
    )
    fn = next(item for item in tool.kwargs["tools"] if item.__name__ == "investigate_exception")
    assert fn("not-an-exception") == {
        "status": "out_of_scope",
        "reason": "invalid synthetic exception identifier",
    }
    assert calls == []
    with pytest.raises(ValueError):
        build_receivables_exception_tool(model=EmptyModel(), investigator=Capture())


def test_model_iteration_budget_cooperatively_stops_at_four_and_cancellation() -> None:
    import asyncio

    async def drain(stream):
        async for _ in stream:
            pass

    delegate = EmptyModel()
    wrapped = _BudgetedModel(
        delegate,
        clock=type("Clock", (), {"monotonic": staticmethod(time.monotonic)})(),
        cancelled=lambda: False,
    )
    for _ in range(4):
        asyncio.run(drain(wrapped.stream([], [])))
    with pytest.raises(Exception, match="four-iteration"):
        asyncio.run(drain(wrapped.stream([], [])))
    cancelled = _BudgetedModel(
        delegate,
        clock=type("Clock", (), {"monotonic": staticmethod(time.monotonic)})(),
        cancelled=lambda: True,
    )
    with pytest.raises(Exception, match="cancelled"):
        asyncio.run(drain(cancelled.stream([], [])))


def test_caller_deadline_does_not_claim_to_kill_a_blocked_call() -> None:
    from aria.agents.aria.receivables.engine import InvestigationStopped, InvocationBudget

    ticks = [1.0]
    budget = InvocationBudget.start(lambda: ticks[0], lambda: False, caller_deadline=2.0)
    budget.check(lambda: ticks[0])
    ticks[0] = 2.0
    with pytest.raises(InvestigationStopped, match="deadline"):
        budget.check(lambda: ticks[0])


def test_deadline_and_cancellation_stop_child_tool_scheduling(monkeypatch) -> None:
    import aria.agents.aria.receivables.agent as agent_module
    from aria.agents.aria.receivables.engine import InvestigationStopped

    monkeypatch.setattr(agent_module, "Agent", CapturingAgent)
    monkeypatch.setattr(agent_module, "tool", lambda function: function)

    class ControlledClock:
        value = 10.0

        def monotonic(self) -> float:
            return self.value

    clock = ControlledClock()
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="deadline", correlation_id="deadline"
    )
    investigator = Investigator()
    tool = build_receivables_exception_tool(
        model=EmptyModel(),
        investigator=investigator,
        context=context,
        clock=clock,
        caller_deadline=40.0,
    )
    investigate = next(fn for fn in tool.kwargs["tools"] if fn.__name__ == "investigate_exception")
    clock.value = 40.0
    with pytest.raises(InvestigationStopped, match="deadline"):
        investigate("EXC-SYN-A02")
    assert investigator.calls == []

    cancelled = build_receivables_exception_tool(
        model=EmptyModel(),
        investigator=investigator,
        context=context,
        clock=clock,
        cancelled=lambda: True,
    )
    status = next(fn for fn in cancelled.kwargs["tools"] if fn.__name__ == "get_proposal_status")
    with pytest.raises(InvestigationStopped, match="cancelled"):
        status("EXC-SYN-A02")
    assert investigator.calls == []


def test_structured_model_calls_share_the_four_iteration_budget() -> None:
    import asyncio

    from pydantic import BaseModel

    from aria.agents.aria.receivables.engine import InvestigationStopped

    class Output(BaseModel):
        value: str

    class ControlledClock:
        def monotonic(self) -> float:
            return 1.0

    async def consume(stream) -> None:
        async for _ in stream:
            pass

    delegate = EmptyModel()
    wrapped = _BudgetedModel(delegate, clock=ControlledClock(), cancelled=lambda: False)
    for _ in range(4):
        asyncio.run(consume(wrapped.structured_output(Output, [])))
    with pytest.raises(InvestigationStopped, match="four-iteration"):
        asyncio.run(consume(wrapped.structured_output(Output, [])))


def test_child_model_deadline_stops_next_call_before_scheduling() -> None:
    import asyncio

    from aria.agents.aria.receivables.engine import InvestigationStopped

    class ControlledClock:
        value = 1.0

        def monotonic(self) -> float:
            return self.value

    async def consume(stream) -> None:
        async for _ in stream:
            pass

    clock = ControlledClock()
    delegate = EmptyModel()
    wrapped = _BudgetedModel(delegate, clock=clock, cancelled=lambda: False, caller_deadline=2.0)
    asyncio.run(consume(wrapped.stream([], [])))
    assert delegate.calls == 1
    clock.value = 2.0
    with pytest.raises(InvestigationStopped, match="deadline"):
        asyncio.run(consume(wrapped.stream([], [])))
    assert delegate.calls == 1
