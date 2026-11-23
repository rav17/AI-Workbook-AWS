"""Base worker agent class. Traces: R12."""
from __future__ import annotations
import json
from strands import Agent
from strands.models.bedrock import BedrockModel
from config.models import ExecutionResult, MemoryContext, PlanTask, Status, Confidence, RiskLevel
from config.settings import AgentConfig

_VALID_STATUSES = {s.value for s in Status}
_VALID_CONFIDENCES = {c.value for c in Confidence}
_VALID_RISK_LEVELS = {r.value for r in RiskLevel}


class WorkerAgent:
    """Base class for domain-specific worker agents. Traces: R12."""

    def __init__(self, domain: str, config: AgentConfig, tools: list, system_prompt: str):
        self.domain = domain
        self.model = BedrockModel(
            model_id=config.llm_model_id,
            region_name=config.aws_region,
        )
        self.agent = Agent(
            model=self.model,
            system_prompt=system_prompt,
            tools=tools,
        )

    def execute(self, task: PlanTask, context: MemoryContext) -> ExecutionResult:
        """Execute a task and return structured ExecutionResult.

        Always returns a valid ExecutionResult with status, confidence,
        recommendation, risk_level, and issues. On any error the result
        has status='failure'. Traces: R12.1, R12.3.
        """
        context_str = self._build_context_prompt(task, context)
        try:
            result = self.agent(context_str)
            return self._parse_result(str(result), task)
        except Exception as e:
            return ExecutionResult(
                status=Status.FAILURE,
                confidence=Confidence.LOW,
                recommendation="",
                risk_level=RiskLevel.HIGH,
                issues=[f"Worker execution error: {str(e)}"],
                worker_domain=self.domain,
                task_id=task.task_id,
            )

    # ------------------------------------------------------------------
    # Schema validation (R12.2, R12.3)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_result(result: ExecutionResult) -> tuple[bool, list[str]]:
        """Validate that an ExecutionResult conforms to the required schema.

        Returns (is_valid, list_of_errors).  The Coordinator calls this
        before reflection to enforce R12.2 / R12.3.
        """
        errors: list[str] = []

        if result.status not in _VALID_STATUSES:
            errors.append(f"Invalid status: {result.status!r}")
        if result.confidence not in _VALID_CONFIDENCES:
            errors.append(f"Invalid confidence: {result.confidence!r}")
        if result.risk_level not in _VALID_RISK_LEVELS:
            errors.append(f"Invalid risk_level: {result.risk_level!r}")
        if not isinstance(result.recommendation, str):
            errors.append("recommendation must be a string")
        if not isinstance(result.issues, list):
            errors.append("issues must be a list")

        return (len(errors) == 0, errors)

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_context_prompt(self, task: PlanTask, context: MemoryContext) -> str:
        parts = [f"Task: {task.intent}"]
        if task.context_hints:
            parts.append(f"Context hints: {task.context_hints}")
        if context.recent_failures:
            failures_summary = "; ".join(
                f"[FAILED: {f.strategy_used or f.output[:80]}]"
                for f in context.recent_failures[:3]
            )
            parts.append(f"Past failures to AVOID: {failures_summary}")
        if context.similar_patterns:
            patterns_summary = "; ".join(
                f"[PATTERN: {p.content[:80]}, score={p.similarity_score:.2f}]"
                for p in context.similar_patterns[:3]
            )
            parts.append(f"Relevant patterns: {patterns_summary}")
        parts.append(
            "Respond with ONLY a JSON object: "
            '{"status":"success/failure","confidence":"high/medium/low",'
            '"recommendation":"...","risk_level":"low/medium/high",'
            '"issues":[],"explainability_summary":"..."}'
        )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Result parsing (R12.1, R12.3)
    # ------------------------------------------------------------------

    def _parse_result(self, raw: str, task: PlanTask) -> ExecutionResult:
        """Parse LLM output into ExecutionResult.

        If the JSON is malformed or required fields contain invalid enum
        values the result is treated as a failure (R12.3).
        """
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                status = data.get("status", "")
                confidence = data.get("confidence", "")
                risk_level = data.get("risk_level", "")

                # R12.3 – missing or invalid fields → failure
                invalid_fields: list[str] = []
                if status not in _VALID_STATUSES:
                    invalid_fields.append(f"status={status!r}")
                if confidence not in _VALID_CONFIDENCES:
                    invalid_fields.append(f"confidence={confidence!r}")
                if risk_level not in _VALID_RISK_LEVELS:
                    invalid_fields.append(f"risk_level={risk_level!r}")

                if invalid_fields:
                    return ExecutionResult(
                        status=Status.FAILURE,
                        confidence=Confidence.LOW,
                        recommendation=data.get("recommendation", ""),
                        risk_level=RiskLevel.HIGH,
                        issues=[f"Invalid ExecutionResult fields: {', '.join(invalid_fields)}"],
                        worker_domain=self.domain,
                        task_id=task.task_id,
                    )

                return ExecutionResult(
                    status=status,
                    confidence=confidence,
                    recommendation=data.get("recommendation", ""),
                    risk_level=risk_level,
                    issues=data.get("issues", []),
                    explainability_summary=data.get("explainability_summary", ""),
                    worker_domain=self.domain,
                    task_id=task.task_id,
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Fallback: no valid JSON found → failure (R12.3)
        return ExecutionResult(
            status=Status.FAILURE,
            confidence=Confidence.LOW,
            recommendation=raw[:500] if raw else "",
            risk_level=RiskLevel.HIGH,
            issues=["Failed to parse structured ExecutionResult from worker output"],
            explainability_summary="",
            worker_domain=self.domain,
            task_id=task.task_id,
        )
