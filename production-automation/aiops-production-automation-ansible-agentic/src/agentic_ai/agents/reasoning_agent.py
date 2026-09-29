"""AI Reasoning Agent — invokes Bedrock for intelligent remediation planning.

Retrieves historical context, builds prompts, invokes Bedrock models,
and falls back to rule-based matching on failure.

Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 9.2
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from src.agentic_ai.models.domain import IncidentRecord, RemediationPlan, RemediationStep
from src.agentic_ai.models.enums import FallbackReason

logger = logging.getLogger(__name__)

REASONING_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 1.0
DEFAULT_MAX_INPUT_TOKENS = 4000
MIN_INPUT_TOKENS = 1000
MAX_INPUT_TOKENS = 16000
MAX_HISTORICAL_INCIDENTS = 50


@dataclass
class AgentConfig:
    """Configuration for the AI Reasoning Agent."""

    model_id: str = ""  # Read from env; falls back to Nova Pro if Claude unavailable
    max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS
    max_output_tokens: int = 2048
    confidence_threshold: float = 0.7
    p1_confidence_threshold: float = 0.8
    temperature: float = 0.2
    region_name: str = "us-east-1"

    # Bedrock Guardrails (optional - provides defense-in-depth content filtering)
    # Set via env vars BEDROCK_GUARDRAIL_ID and BEDROCK_GUARDRAIL_VERSION
    guardrail_id: str = ""
    guardrail_version: str = ""

    # Ordered list of models to try (first available wins)
    FALLBACK_MODELS = [
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "amazon.nova-pro-v1:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
        "amazon.nova-lite-v1:0",
    ]

    def __post_init__(self) -> None:
        if not self.model_id:
            self.model_id = os.environ.get(
                "BEDROCK_MODEL_ID", self.FALLBACK_MODELS[0]
            )
        if not self.guardrail_id:
            self.guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "")
        if not self.guardrail_version:
            self.guardrail_version = os.environ.get("BEDROCK_GUARDRAIL_VERSION", "")
        if self.max_input_tokens < MIN_INPUT_TOKENS or self.max_input_tokens > MAX_INPUT_TOKENS:
            self.max_input_tokens = DEFAULT_MAX_INPUT_TOKENS
        if not (0.0 <= self.confidence_threshold <= 1.0):
            self.confidence_threshold = 0.7
        if not (0.0 <= self.p1_confidence_threshold <= 1.0):
            self.p1_confidence_threshold = 0.8


class AIReasoningAgent:
    """AI-powered reasoning agent using Amazon Bedrock.

    Retrieves incident history, builds a structured prompt, invokes
    the model, parses the response into a RemediationPlan, and falls
    back to rule-based matching on failure.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        incident_store=None,
        playbook_mapper=None,
        bedrock_client=None,
    ) -> None:
        self._config = config or AgentConfig()
        self._incident_store = incident_store
        self._playbook_mapper = playbook_mapper

        if bedrock_client:
            self._client = bedrock_client
        else:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self._config.region_name,
            )

    async def reason(
        self,
        alert_name: str,
        severity: str,
        service_name: str,
        target_resource: str,
        labels: dict[str, str],
        incident_id: str = "",
    ) -> RemediationPlan:
        """Perform AI reasoning to produce a remediation plan.

        Steps:
        1. Retrieve history from incident store
        2. Classify alert complexity for model routing
        3. Build prompt with context (structured for prompt caching)
        4. Invoke Bedrock model (with retry + escalation)
        5. Parse response into RemediationPlan
        6. Fallback to rule-based on failure

        Args:
            alert_name: Name of the triggering alert.
            severity: Alert severity (P1-P5).
            service_name: Affected service.
            target_resource: Target resource identifier.
            labels: Alert labels for context.
            incident_id: Unique incident identifier.

        Returns:
            RemediationPlan with steps and confidence score.
        """
        # Retrieve history
        history = self._get_history(alert_name, severity, service_name)

        # --- Model Routing: classify complexity for cost optimization ---
        from src.agentic_ai.agents.model_router import ModelRouter, AlertComplexity
        router = ModelRouter()
        historical_count = len(history)
        success_count = sum(1 for h in history if h.outcome == "success")
        success_rate = success_count / max(historical_count, 1)
        all_failed = historical_count > 0 and success_count == 0

        routing_decision = router.classify(
            alert_name=alert_name,
            severity=severity,
            historical_count=historical_count,
            historical_success_rate=success_rate,
            correlation_group_size=1,  # Single alert; correlator handles groups
            all_past_failed=all_failed,
        )
        logger.info(
            "Model routing: alert=%s complexity=%s model=%s reason=%s",
            alert_name,
            routing_decision.complexity.value,
            routing_decision.model_id,
            routing_decision.reason,
        )

        # Build prompt (structured for prompt caching — stable prefix + variable suffix)
        prompt = self._build_prompt(
            alert_name, severity, service_name, target_resource, labels, history
        )

        # Invoke with retry and timeout, using the routed model
        fallback_reason: Optional[FallbackReason] = None
        try:
            response_text = await self._invoke_with_retry(
                prompt, primary_model_id=routing_decision.model_id
            )
            plan = self._parse_response(
                response_text, incident_id, target_resource, severity, history
            )

            # --- Model Escalation: if cheap model produced low confidence, re-invoke ---
            if (
                routing_decision.allow_escalation
                and plan.confidence_score < 0.5
                and routing_decision.complexity != AlertComplexity.COMPLEX
            ):
                escalation_model = router.get_escalation_model(routing_decision.complexity)
                if escalation_model:
                    logger.info(
                        "Model escalation: confidence=%.2f < 0.5, escalating to %s",
                        plan.confidence_score,
                        escalation_model,
                    )
                    response_text = await self._invoke_with_retry(
                        prompt, primary_model_id=escalation_model
                    )
                    plan = self._parse_response(
                        response_text, incident_id, target_resource, severity, history
                    )

            return plan
        except TimeoutError:
            fallback_reason = FallbackReason.REASONING_TIMEOUT
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if "Throttl" in error_code:
                fallback_reason = FallbackReason.THROTTLING
            else:
                fallback_reason = FallbackReason.SERVICE_ERROR
        except (BotoCoreError, Exception) as e:
            logger.error("AI reasoning failed: %s", e)
            fallback_reason = FallbackReason.SERVICE_ERROR

        # Fallback to rule-based
        logger.warning(
            "Falling back to rule-based matching (reason: %s)",
            fallback_reason.value if fallback_reason else "unknown",
        )
        return self._fallback(
            incident_id, alert_name, target_resource, fallback_reason
        )

    def _get_history(
        self, alert_name: str, severity: str, service_name: str
    ) -> list[IncidentRecord]:
        """Retrieve historical incidents from the memory store."""
        if self._incident_store is None:
            return []
        try:
            return self._incident_store.query_history(
                alert_name=alert_name,
                severity=severity,
                service=service_name,
                limit=MAX_HISTORICAL_INCIDENTS,
            )
        except Exception as e:
            logger.warning("Failed to retrieve history: %s", e)
            return []

    def _build_prompt(
        self,
        alert_name: str,
        severity: str,
        service_name: str,
        target_resource: str,
        labels: dict[str, str],
        history: list[IncidentRecord],
    ) -> str:
        """Build structured prompt with alert context and history.

        Enforces max_input_tokens by truncating history by recency.
        """
        # Count success/failure for historical context
        success_count = sum(1 for h in history if h.outcome == "success")
        failure_count = sum(1 for h in history if h.outcome == "failure")

        # Identify actions that always failed
        action_outcomes: dict[str, list[str]] = {}
        for h in history:
            if h.alert_name == alert_name:
                outcomes = action_outcomes.setdefault(h.remediation_action, [])
                outcomes.append(h.outcome)

        excluded_actions = [
            action for action, outcomes in action_outcomes.items()
            if outcomes and all(o == "failure" for o in outcomes)
        ]

        # Build history context (truncate to fit token budget)
        history_text = ""
        included = 0
        for record in history[:MAX_HISTORICAL_INCIDENTS]:
            entry = (
                f"- {record.alert_name} | {record.remediation_action} | "
                f"{record.outcome} | {record.execution_duration_seconds:.1f}s\n"
            )
            if len(history_text) + len(entry) > self._config.max_input_tokens * 2:
                break
            history_text += entry
            included += 1

        exclusion_text = ""
        if excluded_actions:
            exclusion_text = (
                f"\nEXCLUDED ACTIONS (all past attempts failed): "
                f"{', '.join(excluded_actions)}\n"
            )

        prompt = f"""You are an AI remediation agent. Analyze the alert and produce a remediation plan.

ALERT CONTEXT:
- Alert Name: {alert_name}
- Severity: {severity}
- Service: {service_name}
- Target Resource: {target_resource}
- Labels: {json.dumps(labels)}

HISTORICAL CONTEXT ({included} incidents, {success_count} successes, {failure_count} failures):
{history_text}
{exclusion_text}
Respond with a JSON object:
{{
  "action": "remediation action name",
  "target": "target resource",
  "confidence": 0.0-1.0,
  "reasoning": "explanation (max 2048 chars)",
  "steps": [{{"step_number": 1, "action": "...", "target_resource": "...", "expected_outcome": "..."}}]
}}"""
        return prompt

    async def _invoke_with_retry(self, prompt: str, primary_model_id: str = "") -> str:
        """Invoke Bedrock with retry, timeout, and model fallback.

        Tries the primary model first (from model router or config).
        If it fails with AccessDenied or ModelNotFound, tries fallback models.

        Args:
            prompt: The prompt to send to the model.
            primary_model_id: The preferred model (from model routing).
                Falls back to self._config.model_id if empty.
        """
        import asyncio

        primary = primary_model_id or self._config.model_id
        models_to_try = [primary] + [
            m for m in self._config.FALLBACK_MODELS
            if m != primary
        ]

        for model_id in models_to_try:
            backoff = INITIAL_BACKOFF_SECONDS
            for attempt in range(MAX_RETRIES + 1):
                try:
                    result = await asyncio.wait_for(
                        self._invoke_model(prompt, model_id=model_id),
                        timeout=REASONING_TIMEOUT_SECONDS,
                    )
                    if model_id != self._config.model_id:
                        logger.info("Using fallback model: %s", model_id)
                    return result
                except asyncio.TimeoutError:
                    if attempt == MAX_RETRIES:
                        break  # Try next model
                    logger.warning("Reasoning attempt %d timed out", attempt + 1)
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code in ("AccessDeniedException", "ValidationException",
                                      "ResourceNotFoundException"):
                        logger.warning(
                            "Model %s unavailable (%s), trying next",
                            model_id, error_code,
                        )
                        break  # Try next model
                    elif "Throttl" in error_code and attempt < MAX_RETRIES:
                        logger.warning("Throttled, retrying in %.1fs", backoff)
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        raise

        raise TimeoutError("All models exhausted")

    async def _invoke_model(self, prompt: str, model_id: str = "") -> str:
        """Invoke the Bedrock model."""
        import asyncio

        if not model_id:
            model_id = self._config.model_id

        # Build request body based on model type
        if "anthropic" in model_id:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self._config.max_output_tokens,
                "temperature": self._config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            })
        else:
            # Amazon Nova models use the messages API format
            body = json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "maxTokens": self._config.max_output_tokens,
                    "temperature": self._config.temperature,
                },
            })

        loop = asyncio.get_event_loop()

        # Build invoke_model kwargs — optionally include Bedrock Guardrails
        invoke_kwargs = {
            "modelId": model_id,
            "body": body,
            "contentType": "application/json",
            "accept": "application/json",
        }

        # Add Bedrock Guardrails if configured (defense-in-depth content filtering)
        if self._config.guardrail_id and self._config.guardrail_version:
            invoke_kwargs["guardrailIdentifier"] = self._config.guardrail_id
            invoke_kwargs["guardrailVersion"] = self._config.guardrail_version

        response = await loop.run_in_executor(
            None,
            lambda: self._client.invoke_model(**invoke_kwargs),
        )

        response_body = json.loads(response["body"].read())

        # Record Bedrock call for tracing (OpenTelemetry GenAI semantic conventions)
        try:
            from src.tracing import trace_bedrock_call

            # Extract token usage if available in response
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0) or usage.get("inputTokens", 0)
            output_tokens = usage.get("output_tokens", 0) or usage.get("outputTokens", 0)

            trace_bedrock_call(
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=True,
            )
        except Exception:
            pass  # Tracing failure must never block the pipeline

        # Parse response based on model type
        if "anthropic" in model_id:
            content = response_body.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
        else:
            # Amazon Nova response format
            output = response_body.get("output", {})
            if isinstance(output, dict):
                message = output.get("message", {})
                content = message.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text", "")
            # Fallback for other formats
            results = response_body.get("results", [])
            if results:
                return results[0].get("outputText", "")
            return str(response_body)

        return ""

    def _parse_response(
        self,
        response_text: str,
        incident_id: str,
        target_resource: str,
        severity: str,
        history: list[IncidentRecord],
    ) -> RemediationPlan:
        """Parse model response into a RemediationPlan."""
        try:
            # Extract JSON from response
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response_text[start:end])
            else:
                raise ValueError("No valid JSON in model response")

        confidence = float(data.get("confidence", 0.5))
        reasoning = str(data.get("reasoning", ""))[:2048]
        action = str(data.get("action", "unknown"))
        target = str(data.get("target", target_resource))

        steps = []
        for s in data.get("steps", []):
            steps.append(RemediationStep(
                step_number=int(s.get("step_number", len(steps) + 1)),
                action=str(s.get("action", action)),
                target_resource=str(s.get("target_resource", target)),
                expected_outcome=str(s.get("expected_outcome", "")),
            ))

        if not steps:
            steps = [RemediationStep(
                step_number=1,
                action=action,
                target_resource=target,
            )]

        # Determine escalation threshold
        threshold = self._config.confidence_threshold
        if severity == "P1":
            threshold = self._config.p1_confidence_threshold

        # Check truncation
        truncation_flag = len(response_text) >= self._config.max_output_tokens * 3

        return RemediationPlan(
            incident_ids=[incident_id] if incident_id else [],
            steps=steps[:20],
            confidence_score=min(max(confidence, 0.0), 1.0),
            reasoning_explanation=reasoning,
            selected_action=action,
            target_resource=target,
            requires_escalation=(confidence < threshold),
            truncation_flag=truncation_flag,
        )

    def _fallback(
        self,
        incident_id: str,
        alert_name: str,
        target_resource: str,
        reason: Optional[FallbackReason],
    ) -> RemediationPlan:
        """Produce a fallback RemediationPlan using rule-based matching."""
        action = "manual_triage"
        if self._playbook_mapper:
            try:
                match = self._playbook_mapper.match_by_alert_name(alert_name)
                if match:
                    action = match.rule_name
            except Exception:
                pass

        return RemediationPlan(
            incident_ids=[incident_id] if incident_id else [],
            steps=[RemediationStep(
                step_number=1,
                action=action,
                target_resource=target_resource,
            )],
            confidence_score=0.0,
            reasoning_explanation=f"Fallback: {reason.value if reason else 'unknown'}",
            selected_action=action,
            target_resource=target_resource,
            requires_escalation=True,
            fallback_used=True,
            fallback_reason=reason,
        )
