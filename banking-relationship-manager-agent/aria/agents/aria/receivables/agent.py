from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncGenerator, AsyncIterable, Callable
from typing import Any, TypeVar, cast

from pydantic import BaseModel
from strands import Agent, tool
from strands.hooks import BeforeInvocationEvent, HookProvider, HookRegistry
from strands.models import Model
from strands.types.content import Messages, SystemContentBlock
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

from aria.agents.aria.receivables.engine import InvestigationStopped, InvocationBudget
from aria.agents.aria.receivables.models import TrustedContext
from aria.agents.aria.receivables.trusted_context import context_from_provider, require_context

T = TypeVar("T", bound=BaseModel)
MAX_INPUT_CHARS = 4_000
MAX_TOOL_OUTPUT_CHARS = 16_000
EXCEPTION_ID_RE = re.compile(r"^EXC-SYN-[A-Z0-9]{3,8}$")


def should_route_receivables_request(text: str) -> bool:
    normalized = (text or "").lower()
    return any(
        token in normalized
        for token in (
            "receivable exception",
            "payment exception",
            "virtual account",
            "unapplied payment",
        )
    )


class _BudgetedModel(Model):
    """Count child model calls cooperatively; do not claim in-flight sync calls can be killed."""

    def __init__(
        self,
        delegate: Model,
        *,
        clock: Any,
        cancelled: Callable[[], bool],
        caller_deadline: float | None = None,
        budget: InvocationBudget | None = None,
    ) -> None:
        self.delegate = delegate
        self.clock = clock
        self.cancelled = cancelled
        self.budget = budget or InvocationBudget.start(clock.monotonic, cancelled, caller_deadline)

    def update_config(self, **model_config: Any) -> None:
        self.delegate.update_config(**model_config)

    def get_config(self) -> Any:
        return self.delegate.get_config()

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if len(str(prompt)) > MAX_INPUT_CHARS:
            raise InvestigationStopped("specialist input exceeds the bounded engineering limit")
        self.budget.check(self.clock.monotonic, model_iteration=True)
        async for event in self.delegate.structured_output(
            output_model, prompt, system_prompt, **kwargs
        ):
            yield event

    async def _events(
        self, source: AsyncIterable[StreamEvent]
    ) -> AsyncGenerator[StreamEvent, None]:
        async for event in source:
            yield event

    def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        if len(str(messages)) > MAX_INPUT_CHARS:

            async def oversized() -> AsyncGenerator[StreamEvent, None]:
                raise InvestigationStopped("specialist input exceeds the bounded engineering limit")
                yield {}  # pragma: no cover

            return oversized()
        try:
            self.budget.check(self.clock.monotonic, model_iteration=True)
        except InvestigationStopped as exc:
            error = exc

            async def stopped() -> AsyncGenerator[StreamEvent, None]:
                raise error
                yield {}  # pragma: no cover

            return stopped()
        source = self.delegate.stream(
            messages,
            tool_specs,
            system_prompt,
            tool_choice=tool_choice,
            system_prompt_content=system_prompt_content,
            invocation_state=invocation_state,
            **kwargs,
        )
        return self._events(source)


def build_receivables_exception_tool(
    *,
    model: Model,
    investigator: Any,
    context: TrustedContext | None = None,
    context_provider: Any | None = None,
    status_reader: Callable[[TrustedContext, str], Any] | None = None,
    clock: Any | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    caller_deadline: float | None = None,
) -> Any:
    """Build a model-facing child tool; identity, decisions, and writes stay in closures."""
    if context is None and context_provider is None:
        raise ValueError("a trusted context or separately trusted provider is required")
    if context is not None:
        require_context(context)
    if context is None:
        bound_context = None
    else:
        bound_context = context
    operation_clock = clock or type("Clock", (), {"monotonic": staticmethod(time.monotonic)})()
    budget = InvocationBudget.start(operation_clock.monotonic, cancelled, caller_deadline)

    def trusted() -> TrustedContext:
        current = (
            context_from_provider(context_provider)
            if context_provider is not None
            else bound_context
        )
        if current is None:
            raise RuntimeError("trusted context is unavailable")
        return require_context(current)

    @tool
    def investigate_exception(exception_id: str) -> dict[str, Any]:
        """Investigate one in-scope synthetic exception using read-only evidence."""
        bounded_model.budget.check(operation_clock.monotonic)
        if not EXCEPTION_ID_RE.fullmatch(exception_id):
            return {"status": "out_of_scope", "reason": "invalid synthetic exception identifier"}
        payment_id = "PAY-SYN-" + exception_id.removeprefix("EXC-SYN-")
        result = investigator.investigate(
            trusted(),
            payment_id,
            cancelled=cancelled,
            caller_deadline=bounded_model.budget.deadline,
        )
        if hasattr(result, "model_dump"):
            rendered = result.model_dump(mode="json")
            if len(str(rendered)) > MAX_TOOL_OUTPUT_CHARS:
                return {
                    "status": "error",
                    "reason": "specialist output exceeds the bounded engineering limit",
                }
            return cast(dict[str, Any], rendered)
        if isinstance(result, dict):
            return (
                cast(dict[str, Any], result)
                if len(str(result)) <= MAX_TOOL_OUTPUT_CHARS
                else {
                    "status": "error",
                    "reason": "specialist output exceeds the bounded engineering limit",
                }
            )
        return {"status": "ok", "result": str(result)[:MAX_TOOL_OUTPUT_CHARS]}

    @tool
    def get_proposal_status(exception_id: str) -> dict[str, Any]:
        """Read the current synthetic proposal status by exception identifier."""
        bounded_model.budget.check(operation_clock.monotonic)
        if not EXCEPTION_ID_RE.fullmatch(exception_id):
            return {"status": "out_of_scope", "reason": "invalid synthetic exception identifier"}
        if status_reader is None:
            return {"status": "unavailable"}
        result = status_reader(trusted(), exception_id)
        rendered = (
            result.model_dump(mode="json")
            if isinstance(result, BaseModel)
            else result
            if isinstance(result, dict)
            else {"status": "ok", "result": str(result)}
        )
        if len(json.dumps(rendered)) > MAX_TOOL_OUTPUT_CHARS:
            return {
                "status": "error",
                "reason": "specialist output exceeds the bounded engineering limit",
            }
        return cast(dict[str, Any], rendered)

    bounded_model = _BudgetedModel(
        model,
        clock=operation_clock,
        cancelled=cancelled,
        caller_deadline=caller_deadline,
        budget=budget,
    )

    class InvocationHooks(HookProvider):
        def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
            registry.add_callback(BeforeInvocationEvent, self.reset)

        def reset(self, event: BeforeInvocationEvent) -> None:
            bounded_model.budget = InvocationBudget.start(
                operation_clock.monotonic, cancelled, caller_deadline
            )

    child = Agent(
        hooks=[InvocationHooks()],
        model=bounded_model,
        name="receivables_exception_investigator",
        system_prompt=(
            "Investigate only synthetic receivables exceptions. Use only closure tools. "
            "Do not infer identity or approval, or claim a write. Facts are authoritative only "
            "when cited; reference and payer-name matches are inference."
        ),
        tools=[investigate_exception, get_proposal_status],
    )
    return child.as_tool(
        name="receivables_exception_investigator",
        description="Investigate an in-scope synthetic receivables exception.",
        preserve_context=False,
    )
