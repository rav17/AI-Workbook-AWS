"""Service Request Handler worker agent. Traces: R28, R29, R32."""
from __future__ import annotations

import uuid

from agents.workers.base import WorkerAgent
from config.models import (
    ExecutionResult,
    EscalationResult,
    MemoryContext,
    PlanTask,
    ServiceRequest,
    Status,
    Confidence,
    RiskLevel,
)
from config.settings import AgentConfig, PriorityConfig
from tools.financial_tools import (
    service_request_processor,
    escalation_tracker,
    document_guidance_tool,
)

SERVICE_REQUEST_SYSTEM_PROMPT = """You are a Service Request Handler agent for a personal banking AI system.
Your job is to process routine banking service requests such as account modifications,
charge disputes, failed transaction inquiries, card issues, document requests, and KYC updates.

When given a task:
1. Use the service_request_processor tool to process the request
2. Use the escalation_tracker tool if the request needs escalation
3. Use the document_guidance_tool for document-related requests
4. Assign priority based on the user's programme tier

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"resolution or next steps","risk_level":"low/medium/high","issues":[],"explainability_summary":"factors considered"}

Set risk_level based on request complexity and financial impact.
"""

# Default priority config used when none is provided
_DEFAULT_PRIORITY_CONFIG = PriorityConfig()


class ServiceRequestHandlerAgent(WorkerAgent):
    """Handles service requests, escalations, and routine banking operations.

    Traces: R28.1, R28.2, R28.3, R28.5, R28.6, R29.1, R32.1.
    """

    def __init__(self, config: AgentConfig, priority_config: PriorityConfig | None = None):
        super().__init__(
            domain="service_request",
            config=config,
            tools=[service_request_processor, escalation_tracker, document_guidance_tool],
            system_prompt=SERVICE_REQUEST_SYSTEM_PROMPT,
        )
        self.priority_config = priority_config or _DEFAULT_PRIORITY_CONFIG

    # ------------------------------------------------------------------
    # Core service request handling (R28.1, R29.1)
    # ------------------------------------------------------------------

    def handle_service_request(
        self, request: ServiceRequest, user_tier: str
    ) -> ExecutionResult:
        """Process a service request with tier-based priority assignment.

        Maps the user's programme tier to a priority level and returns an
        ExecutionResult enriched with priority metadata and a tracking
        reference.  Traces: R28.1, R29.1.
        """
        priority_level = self.priority_config.tier_priority_map.get(
            user_tier, "standard"
        )
        estimated_time = self.priority_config.estimated_processing_times.get(
            priority_level, "3-5 business days"
        )
        tracking_ref = f"SR-{uuid.uuid4().hex[:8].upper()}"

        return ExecutionResult(
            status=Status.SUCCESS,
            confidence=Confidence.HIGH,
            recommendation=(
                f"Service request '{request.request_type}' received and being processed "
                f"with {priority_level} priority. Tracking reference: {tracking_ref}."
            ),
            risk_level=RiskLevel.LOW,
            issues=[],
            explainability_summary=(
                f"Request type: {request.request_type}. "
                f"User tier: {user_tier}. Priority: {priority_level}. "
                f"Estimated processing time: {estimated_time}."
            ),
            worker_domain=self.domain,
            priority_level=priority_level,
            estimated_processing_time=estimated_time,
            tracking_reference=tracking_ref,
        )

    # ------------------------------------------------------------------
    # Escalation (R28.2, R28.3)
    # ------------------------------------------------------------------

    def escalate(self, request: ServiceRequest) -> EscalationResult:
        """Escalate an unresolved service request with tracking and timeline.

        Returns an EscalationResult containing a unique tracking reference,
        estimated resolution timeline, escalation reason, and path.
        Traces: R28.2, R28.3.
        """
        tracking_ref = f"ESC-{uuid.uuid4().hex[:8].upper()}"
        priority_level = request.priority_level or "standard"
        estimated_timeline = self.priority_config.estimated_processing_times.get(
            priority_level, "3-5 business days"
        )

        return EscalationResult(
            tracking_reference=tracking_ref,
            estimated_timeline=estimated_timeline,
            escalation_reason=(
                f"Service request '{request.request_type}' could not be resolved "
                f"at current level. Escalating for further review."
            ),
            escalation_path="senior_support_team",
        )


def create_service_request_handler(
    config: AgentConfig, priority_config: PriorityConfig | None = None
) -> ServiceRequestHandlerAgent:
    """Factory function for ServiceRequestHandlerAgent."""
    return ServiceRequestHandlerAgent(config, priority_config)
