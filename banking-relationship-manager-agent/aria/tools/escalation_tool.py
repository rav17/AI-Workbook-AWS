from __future__ import annotations

from typing import Any

from aria.guardrails.processor import GuardrailProcessor
from aria.observability import Observability


def escalate_request(category: str, context: dict[str, Any]) -> dict[str, Any]:
    category_lower = category.lower()

    if "legal" in category_lower or "fraud" in category_lower or "freeze" in category_lower:
        team = "legal-and-risk"
        priority = "high"
        timeline = "Same business day response; specialist review within 4 hours."
    elif "estate" in category_lower or "treasury" in category_lower:
        team = "private-wealth"
        priority = "medium"
        timeline = "Next business day response with advisor follow-up."
    elif "credit" in category_lower:
        team = "credit-underwriting"
        priority = "high"
        timeline = "Priority review within 1 business day."
    else:
        team = "relationship-team"
        priority = "medium"
        timeline = "Standard response within 2 business days."

    context_fields: dict[str, Any] = {}
    for key in ("session_id", "segment_flags"):
        if key in context:
            context_fields[key] = context[key]
    question = context.get("question")
    if isinstance(question, str):
        guarded_question = GuardrailProcessor().process_input(question)
        context_fields["question"] = (
            guarded_question.sanitized_message if not guarded_question.blocked else "[REDACTED]"
        )

    result = {
        "client_id": context.get("client_id", "unknown"),
        "name": context.get("name", "Unknown"),
        "category": category,
        "team": team,
        "priority": priority,
        "status": "escalated",
        "response_timeline": timeline,
        "context": context_fields,
    }
    Observability().emit_operation(
        "escalation.create",
        {
            "client_id": result["client_id"],
            "team": team,
            "priority": priority,
            "category": category,
        },
        status="escalated",
    )
    return result
