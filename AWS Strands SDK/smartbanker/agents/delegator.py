"""Delegator agent — routes tasks to worker agents. Traces: R2."""
from __future__ import annotations
from config.models import ExecutionResult, Plan, PlanTask, MemoryContext, Status, Confidence, RiskLevel
from config.settings import AgentConfig
from agents.workers.base import WorkerAgent
from tools.registry import ToolRegistry, ToolSchema, create_default_registry
from observability.logger import CorrelatedLogger


# Domain keyword mapping for relevance scoring (R2.4).
# Each key is a worker domain; values are keywords that boost relevance.
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "spending_analysis": ["spend", "transaction", "expense", "purchase", "budget", "category"],
    "savings_advice": ["save", "saving", "deposit", "balance", "budget", "emergency fund"],
    "investment_advice": ["invest", "stock", "bond", "portfolio", "market", "wealth", "forex", "demat"],
    "loan_advice": ["loan", "borrow", "mortgage", "credit", "interest rate", "emi", "financing"],
    "financial_query": ["question", "query", "what is", "how does", "explain", "help"],
    "risk_compliance": ["risk", "compliance", "safety", "regulation", "kyc", "audit"],
    "service_request": ["service", "request", "dispute", "escalat", "card issue", "document", "cheque"],
    "value_assessment": ["value", "tier", "benefit", "upgrade", "downgrade", "assessment"],
}


def _compute_relevance_score(domain: str, intent: str) -> float:
    """Compute a relevance score (0.0–1.0) for a domain against a task intent.

    Exact domain match in the intent gives a perfect score.  Otherwise the
    score is the fraction of domain keywords found in the lowered intent text.
    Traces: R2.4.
    """
    intent_lower = intent.lower()

    # Exact domain name match → highest relevance
    if domain in intent_lower:
        return 1.0

    keywords = _DOMAIN_KEYWORDS.get(domain, [])
    if not keywords:
        return 0.0

    hits = sum(1 for kw in keywords if kw in intent_lower)
    return hits / len(keywords)


class DelegatorAgent:
    """Routes Plan tasks to Worker Agents based on intent matching,
    tool compatibility, and priority level. Traces: R2."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.tool_registry: ToolRegistry = create_default_registry()
        self.workers: dict[str, WorkerAgent] = {}
        self.logger = CorrelatedLogger()

    # ------------------------------------------------------------------
    # Worker registration
    # ------------------------------------------------------------------

    def register_worker(self, domain: str, worker: WorkerAgent) -> None:
        """Register a worker agent for a given domain. Traces: R2.1."""
        self.workers[domain] = worker

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        plan: Plan,
        context: MemoryContext,
        correlation_id: str = "",
        priority_level: str | None = None,
    ) -> list[ExecutionResult]:
        """Dispatch all tasks in a Plan to appropriate workers.

        Tasks are executed in ``execution_order``.  When *priority_level* is
        provided (e.g. ``"critical"``), it is recorded in each result for
        downstream priority-aware processing.  Traces: R2.1, R2.2.
        """
        self.logger = self.logger.with_correlation(correlation_id)
        results: list[ExecutionResult] = []
        sorted_tasks = sorted(plan.tasks, key=lambda t: t.execution_order)

        for task in sorted_tasks:
            route_result = self.route_task(task)

            if isinstance(route_result, ExecutionResult):
                # Routing failed — propagate the error result
                if priority_level:
                    route_result.priority_level = priority_level
                self.logger.log_worker_execution(
                    task.assigned_worker, route_result.status, route_result.confidence
                )
                results.append(route_result)
                continue

            worker, compatible_tools = route_result
            result = worker.execute(task, context)

            if priority_level:
                result.priority_level = priority_level

            self.logger.log_worker_execution(
                worker.domain, result.status, result.confidence
            )
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Routing (R2.1, R2.2, R2.3, R2.4)
    # ------------------------------------------------------------------

    def route_task(
        self, task: PlanTask
    ) -> tuple[WorkerAgent, list[ToolSchema]] | ExecutionResult:
        """Select the best worker and validate tool compatibility.

        Returns ``(worker, compatible_tools)`` on success, or an error
        ``ExecutionResult`` when no compatible worker can be found.

        Routing logic:
        1. Try the explicitly assigned worker first (``task.assigned_worker``).
           If the worker is registered, route to it — tool validation is
           advisory only (the worker already has its tools configured).
        2. If that worker is not registered, fall back to all registered
           workers and pick the one with the highest domain-relevance score
           (R2.4).
        3. If no worker qualifies, return an error ``ExecutionResult`` (R2.3).
        """
        # 1. Try the explicitly assigned worker --------------------------
        primary = self.workers.get(task.assigned_worker)
        if primary is not None:
            # Worker is registered — route to it. Tool validation is advisory;
            # the worker already has its tools configured via its constructor.
            compatible = self.tool_registry.get_compatible_tools(task.assigned_worker)
            return (primary, compatible)

        # 2. Fallback: score all registered workers (R2.4) ---------------
        candidates: list[tuple[float, str, WorkerAgent, list[ToolSchema]]] = []
        for domain, worker in self.workers.items():
            score = _compute_relevance_score(domain, task.intent)
            compatible = self.tool_registry.get_compatible_tools(domain)
            candidates.append((score, domain, worker, compatible))

        if candidates:
            # Highest relevance score wins
            candidates.sort(key=lambda c: c[0], reverse=True)
            _score, _domain, best_worker, best_tools = candidates[0]
            return (best_worker, best_tools)

        # 3. No compatible worker found (R2.3) ---------------------------
        return ExecutionResult(
            status=Status.FAILURE,
            confidence=Confidence.LOW,
            recommendation="",
            risk_level=RiskLevel.HIGH,
            issues=[
                f"No compatible worker found for task '{task.intent}' "
                f"(assigned_worker='{task.assigned_worker}'). "
                "Either the worker is not registered or required tools are incompatible."
            ],
            worker_domain=task.assigned_worker,
            task_id=task.task_id,
        )
