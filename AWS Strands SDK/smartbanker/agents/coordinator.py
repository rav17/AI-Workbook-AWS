"""Coordinator agent — orchestrates the self-healing loop. Traces: R1, R13, R17, R19, R26, R28, R32, R37, R38."""
from __future__ import annotations

import json
import uuid

from strands import Agent
from strands.models.bedrock import BedrockModel

from config.models import (
    EscalationResult,
    ExecutionResult,
    FinalResponse,
    FinancialPattern,
    InteractionRecord,
    IntrospectionReport,
    MemoryContext,
    Plan,
    PlanTask,
    ProactiveNotification,
    ReflectionDecision,
    ServiceRequest,
    Status,
    Confidence,
    RiskLevel,
)
from config.settings import AgentConfig, MemoryConfig
from agents.delegator import DelegatorAgent
from agents.workers.risk_compliance import RiskComplianceAgent
from memory.dynamodb_manager import DynamoDBShortTermMemory
from memory.vector_memory import VectorMemoryManager
from memory.degradation import MemoryDegradationControl
from compliance.disclosure_manager import DisclosureManager
from observability.logger import CorrelatedLogger
from priority.priority_manager import PriorityManager
from engagement.proactive_engine import ProactiveEngagementEngine

COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator agent for a Personal Banker AI system.
Your job is to decompose user financial requests into structured plans.

Given a user request and memory context, produce a Plan as strict JSON:
{
  "tasks": [
    {
      "intent": "description of what needs to be done",
      "assigned_worker": "one of: spending_analysis, savings_advice, investment_advice, financial_query, risk_compliance",
      "execution_order": 0,
      "required_tools": ["tool_name"],
      "context_hints": "relevant context for the worker"
    }
  ],
  "excluded_strategies": ["strategies to avoid based on past failures"]
}

Worker domains:
- spending_analysis: analyze transactions, detect spending patterns
- savings_advice: suggest saving strategies
- investment_advice: provide risk-aware investment recommendations
- financial_query: answer financial questions
- risk_compliance: validate recommendations for safety

Rules:
1. Consider user financial history from memory context
2. AVOID past failed strategies listed in context
3. Personalize based on user patterns
4. Return ONLY valid JSON
"""


REFLECTION_PROMPT = """You are reflecting on execution results from worker agents.
Analyze these results and decide whether to retry or finalize.

Results: {results}

Respond with ONLY JSON:
{{
  "action": "retry" or "finalize",
  "reason": "explanation",
  "failed_tasks": ["ids of failed tasks"]
}}

Retry if: any result has status=failure or confidence=low with fixable issues.
Do NOT retry if: all results are success with medium/high confidence, or issues are unfixable.
"""


class CoordinatorAgent:
    """Orchestrates the self-healing loop:
    memory → plan → delegate → execute → introspect → reflect → retry → persist.

    Acts as the single point of contact (virtual relationship manager) for all
    banking needs including service requests, escalations, and proactive engagement.

    Traces: R1, R13, R17, R19, R26, R28, R32, R37, R38.
    """

    def __init__(self, agent_config: AgentConfig, memory_config: MemoryConfig):
        # LLM model for planning via Strands Agent. Traces: R16.1
        self.model = BedrockModel(
            model_id=agent_config.llm_model_id,
            region_name=agent_config.aws_region,
        )
        self.planner = Agent(
            model=self.model,
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            tools=[],
        )

        # Sub-agents and memory components
        self.delegator = DelegatorAgent(agent_config)
        self.stm = DynamoDBShortTermMemory(memory_config)
        self.ltm = VectorMemoryManager(config=memory_config)
        self.degradation = MemoryDegradationControl(memory_config)

        # Compliance
        self.risk_agent: RiskComplianceAgent | None = None
        self.disclosure = DisclosureManager()

        # Phase 2: Priority Manager (R29)
        self.priority_manager = PriorityManager()

        # Phase 2: Proactive Engagement Engine (R37)
        self.proactive_engine = ProactiveEngagementEngine()

        # Retry budget. Traces: R13.4
        self.max_retries = agent_config.max_retries

        # Observability. Traces: R14.4
        self.logger = CorrelatedLogger()

    # ------------------------------------------------------------------
    # Main entry point — self-healing loop. Traces: R17.1, R17.2
    # ------------------------------------------------------------------

    def process_request(self, user_id: str, request: str) -> FinalResponse:
        """Execute the full self-healing loop.

        Flow: generate correlation_id → retrieve memory → plan → delegate →
              introspect → compliance check → reflect → retry if needed →
              persist learnings → return FinalResponse.

        Traces: R17.1, R17.2, R17.3, R17.4.
        """
        # Step 1: Generate correlation_id for end-to-end tracing
        correlation_id = str(uuid.uuid4())
        self.logger = self.logger.with_correlation(correlation_id)

        # Step 2: Retrieve memory (STM failures + LTM patterns). Traces: R1.3
        context = self._retrieve_memory(user_id, request)

        retries_used = 0
        all_results: list[ExecutionResult] = []

        for attempt in range(self.max_retries + 1):
            # Step 3: Plan — decompose request into tasks. Traces: R1.1, R1.2
            plan = self.plan(context, request, user_id)
            self.logger.log_plan_generated(plan.plan_id, len(plan.tasks))

            # Step 4: Delegate + Execute. Traces: R2
            results = self.delegator.dispatch(plan, context, correlation_id)

            # Step 5: Introspect — validate each result. Traces: R12.2
            for i, r in enumerate(results):
                report = self.introspect(r)
                if not report.schema_valid:
                    results[i].status = Status.FAILURE
                    results[i].issues.extend(report.issues)

            # Step 6: Compliance check. Traces: R7.1
            results = [self._compliance_check(r) for r in results]

            # Step 6.5: Apply disclosures. Traces: R15
            results = [self.disclosure.apply_disclosures(r) for r in results]

            all_results = results

            # Step 7: Reflect — decide retry vs finalize. Traces: R13.1, R13.2
            reflection = self.reflect(results)
            self.logger.log_reflection(reflection.should_retry, reflection.reason)

            if not reflection.should_retry or attempt >= self.max_retries:
                break

            # Step 8: Retry with improved strategy. Traces: R13.3
            retries_used = attempt + 1
            # Enrich context with failure info for next planning attempt
            failed_results = [r for r in results if r.status == Status.FAILURE]
            new_failures = []
            for r in failed_results:
                new_failures.append(InteractionRecord(
                    user_id=user_id,
                    input=request,
                    output=r.recommendation[:500],
                    status="failure",
                    confidence=r.confidence,
                    strategy_used=r.explainability_summary[:200],
                    worker_domain=r.worker_domain,
                ))
            # Rebuild context with additional failures
            combined_failures = list(context.failures) + new_failures
            context = self.degradation.prepare_context(
                combined_failures, context.patterns, current_intent=request[:50],
            )

        # Step 9: Persist learnings to STM + LTM. Traces: R13.5
        self._persist_learnings(user_id, request, all_results, correlation_id)

        # Step 10: Build and return FinalResponse. Traces: R17.4
        status = self._determine_overall_status(all_results)
        warnings = []
        for r in all_results:
            if r.issues:
                warnings.append(r.issues[0])

        return FinalResponse(
            correlation_id=correlation_id,
            user_id=user_id,
            status=status,
            recommendations=all_results,
            retries_used=retries_used,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Planning. Traces: R1.1, R1.2, R1.4, R1.5
    # ------------------------------------------------------------------

    def plan(
        self, context: MemoryContext, request: str, user_id: str = ""
    ) -> Plan:
        """Decompose a user request into a structured Plan via LLM.

        Uses memory context to exclude failed strategies (R1.4) and
        personalize based on user patterns (R1.5).

        Traces: R1.1, R1.2, R1.4, R1.5.
        """
        prompt_parts = [f"User request: {request}"]

        # R1.4: Exclude previously failed strategies
        if context.failures:
            failed_strategies = [
                f.strategy_used or f.output[:80] for f in context.failures
            ]
            prompt_parts.append(
                f"AVOID these past failed strategies: {failed_strategies}"
            )
            # R14.3: Log avoided mistakes
            for f in context.failures:
                self.logger.log_avoided_mistake(f.correlation_id, request[:80])

        # R1.5: Personalize based on user patterns
        if context.patterns:
            prompt_parts.append(
                f"Relevant patterns: {[p.content[:80] for p in context.patterns]}"
            )

        prompt = "\n".join(prompt_parts)

        try:
            result = self.planner(prompt)
            raw = str(result)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                tasks = [PlanTask(**t) for t in data.get("tasks", [])]
                return Plan(
                    user_id=user_id,
                    original_request=request,
                    tasks=tasks,
                    excluded_strategies=data.get("excluded_strategies", []),
                )
        except Exception:
            pass

        # Fallback: single-task plan routed to financial_query
        return Plan(
            user_id=user_id,
            original_request=request,
            tasks=[
                PlanTask(
                    intent=request,
                    assigned_worker="financial_query",
                    execution_order=0,
                )
            ],
        )

    # ------------------------------------------------------------------
    # Reflection. Traces: R13.1, R13.2
    # ------------------------------------------------------------------

    def reflect(self, results: list[ExecutionResult]) -> ReflectionDecision:
        """Analyze execution results for failures and decide retry vs finalize.

        Retry when there are fixable failures (not compliance rejections).
        Finalize when all results are acceptable or failures are unfixable.

        Traces: R13.1, R13.2.
        """
        failed = [
            r for r in results
            if r.status == Status.FAILURE or r.confidence == Confidence.LOW
        ]

        if not failed:
            return ReflectionDecision(
                action="finalize",
                reason="All results successful with acceptable confidence",
            )

        # Compliance violations are not retryable
        fixable = [
            r for r in failed
            if not any("Compliance violation" in issue for issue in r.issues)
        ]

        if not fixable:
            return ReflectionDecision(
                action="finalize",
                reason="Failures are compliance-related and not retryable",
            )

        return ReflectionDecision(
            action="retry",
            reason=f"{len(fixable)} tasks failed with potentially fixable issues",
            failed_tasks=[r.task_id for r in fixable],
        )

    # ------------------------------------------------------------------
    # Introspection. Traces: R12.2, R12.3
    # ------------------------------------------------------------------

    def introspect(self, result: ExecutionResult) -> IntrospectionReport:
        """Validate an ExecutionResult for schema conformance and quality.

        Returns an IntrospectionReport indicating whether the result is
        schema-valid and listing any issues found.

        Traces: R12.2, R12.3.
        """
        issues: list[str] = []

        try:
            ExecutionResult.model_validate(result.model_dump())
        except Exception as exc:
            issues.append(f"Schema validation failed: {exc}")

        # Quality checks
        if not result.recommendation:
            issues.append("Empty recommendation")
        if not result.worker_domain:
            issues.append("Missing worker_domain")

        schema_valid = len(issues) == 0
        quality = "high" if schema_valid and result.confidence != Confidence.LOW else "low"

        return IntrospectionReport(
            schema_valid=schema_valid,
            quality_score=quality,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _retrieve_memory(self, user_id: str, request: str) -> MemoryContext:
        """Retrieve and filter memory context from STM + LTM.

        Traces: R1.3, R11.
        """
        try:
            failures = self.stm.get_failures(user_id)
        except Exception:
            failures = []

        try:
            patterns = self.ltm.search_patterns(request, user_id=user_id)
        except Exception:
            patterns = []

        # R14.2: Log pattern reuse
        for p in patterns:
            self.logger.log_pattern_reuse(p.pattern_id, p.similarity_score)

        # R11: Apply degradation control
        return self.degradation.prepare_context(
            failures, patterns, current_intent=request[:50]
        )

    def _compliance_check(self, result: ExecutionResult) -> ExecutionResult:
        """Run compliance validation on a result. Traces: R7.1."""
        if self.risk_agent and result.status == Status.SUCCESS:
            return self.risk_agent.validate_recommendation(result)
        return result

    def _persist_learnings(
        self,
        user_id: str,
        request: str,
        results: list[ExecutionResult],
        correlation_id: str,
    ) -> None:
        """Persist interaction records to STM and patterns to LTM.

        Traces: R13.5.
        """
        for r in results:
            # STM: store every interaction
            record = InteractionRecord(
                user_id=user_id,
                input=request,
                output=r.recommendation[:500],
                status=r.status,
                confidence=r.confidence,
                intent=r.worker_domain,
                worker_domain=r.worker_domain,
                strategy_used=r.explainability_summary[:200] if r.explainability_summary else "",
                correlation_id=correlation_id,
                channel_id="",  # populated by caller when channel context is available
                priority_level=r.priority_level,
            )
            try:
                self.stm.store_interaction(user_id, record)
            except Exception:
                pass

            # LTM: store failures and non-high-confidence results as patterns
            if r.status == Status.FAILURE or r.confidence != Confidence.HIGH:
                pattern = FinancialPattern(
                    user_id=user_id,
                    pattern_type="failure" if r.status == Status.FAILURE else "recommendation",
                    content=f"Request: {request[:200]} | Result: {r.recommendation[:200]}",
                    metadata={
                        "risk_level": r.risk_level,
                        "confidence": r.confidence,
                        "worker_domain": r.worker_domain,
                        "outcome": r.status,
                    },
                )
                try:
                    self.ltm.store_pattern(pattern)
                except Exception:
                    pass

    @staticmethod
    def _determine_overall_status(
        results: list[ExecutionResult],
    ) -> str:
        """Determine the overall response status from individual results."""
        if not results:
            return "failure"
        if all(r.status == Status.FAILURE for r in results):
            return "failure"
        if any(r.status == Status.FAILURE for r in results):
            return "partial_success"
        return "success"

    # ------------------------------------------------------------------
    # Phase 2: Service request handling (R28). Traces: R28.1
    # ------------------------------------------------------------------

    def handle_service_request(
        self, user_id: str, service_request: ServiceRequest
    ) -> FinalResponse:
        """Route service requests to appropriate worker or escalation path.

        Stores request in STM for continuity. Traces: R28.1.
        """
        correlation_id = str(uuid.uuid4())
        self.logger = self.logger.with_correlation(correlation_id)

        # Create a plan task for the service request
        task = PlanTask(
            intent=f"service_request:{service_request.request_type} - {service_request.description}",
            assigned_worker="service_request",
            execution_order=0,
            required_tools=["service_request_processor"],
        )
        plan = Plan(
            user_id=user_id,
            original_request=service_request.description,
            tasks=[task],
        )

        context = self._retrieve_memory(user_id, service_request.description)
        results = self.delegator.dispatch(plan, context, correlation_id)

        # Persist the interaction
        self._persist_learnings(user_id, service_request.description, results, correlation_id)

        status = self._determine_overall_status(results)
        return FinalResponse(
            correlation_id=correlation_id,
            user_id=user_id,
            status=status,
            recommendations=results,
        )

    # ------------------------------------------------------------------
    # Phase 2: Escalation (R28.2, R28.3)
    # ------------------------------------------------------------------

    def escalate(
        self, user_id: str, service_request: ServiceRequest
    ) -> EscalationResult:
        """Escalate unresolved issues via Service_Escalation workflow.

        Returns tracking reference and timeline. Traces: R28.2, R28.3.
        """
        tracking_ref = f"ESC-{uuid.uuid4().hex[:8].upper()}"
        estimated_timeline = self.priority_manager.get_estimated_time(
            service_request.priority_level or "standard"
        )

        self.logger.log_escalation(
            user_id=user_id,
            service_request_id=service_request.request_id,
            tracking_ref=tracking_ref,
            estimated_timeline=estimated_timeline,
        )

        return EscalationResult(
            tracking_reference=tracking_ref,
            estimated_timeline=estimated_timeline,
            escalation_reason=(
                f"Service request '{service_request.request_type}' escalated "
                f"for further review."
            ),
            escalation_path="senior_support_team",
        )

    # ------------------------------------------------------------------
    # Phase 2: Proactive engagement (R37)
    # ------------------------------------------------------------------

    def check_proactive_opportunities(
        self, user_id: str, tier: str = "basic"
    ) -> list[ProactiveNotification]:
        """Check for proactive engagement opportunities based on user memory patterns.

        Traces: R37.1.
        """
        try:
            interactions = self.stm.retrieve_interactions(user_id)
        except Exception:
            interactions = []

        try:
            patterns = self.ltm.search_patterns("", user_id=user_id)
        except Exception:
            patterns = []

        opportunities = self.proactive_engine.detect_patterns(interactions, patterns)
        notifications: list[ProactiveNotification] = []
        for opp in opportunities:
            notification = self.proactive_engine.generate_notification(opp, user_id)
            self.logger.log_proactive_engagement(
                user_id=user_id,
                opportunity_type=opp.opportunity_type,
                notification_id=notification.notification_id,
            )
            notifications.append(notification)

        return notifications

    # ------------------------------------------------------------------
    # Phase 2: Complex banking operations (R32)
    # ------------------------------------------------------------------

    def decompose_complex_operation(
        self, user_id: str, request: str
    ) -> Plan:
        """Decompose a complex banking operation into multi-worker sub-tasks.

        Ensures risk_compliance is always included for complex operations.
        Traces: R32.2, R32.3.
        """
        # Build a multi-task plan with risk compliance
        tasks = [
            PlanTask(
                intent=request,
                assigned_worker="financial_query",
                execution_order=0,
                context_hints="Complex operation — coordinate across domains",
            ),
            PlanTask(
                intent=f"Compliance check for complex operation: {request}",
                assigned_worker="risk_compliance",
                execution_order=1,
                context_hints="Enhanced compliance check for complex operation",
            ),
        ]
        return Plan(
            user_id=user_id,
            original_request=request,
            tasks=tasks,
        )
