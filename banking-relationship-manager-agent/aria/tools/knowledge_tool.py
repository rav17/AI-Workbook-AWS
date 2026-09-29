from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProductAnswer:
    answer: str
    confidence: float
    source_date: str


def query_product_info(query: str, knowledge: dict[str, Any] | None = None) -> ProductAnswer:
    knowledge = knowledge or {}

    best_match = None
    for key, value in knowledge.items():
        if isinstance(value, dict):
            if key.lower() in query.lower() or query.lower() in key.lower():
                best_match = value
                break

    if best_match is None:
        raise ValueError("No relevant knowledge found for the requested product information.")

    answer = str(best_match.get("answer", "Information unavailable."))
    source_date = str(best_match.get("source_date", "unknown"))
    confidence = float(best_match.get("confidence", 0.0))

    return ProductAnswer(answer=answer, confidence=confidence, source_date=source_date)


def answer_service_query(question: str, knowledge: dict[str, Any] | None = None) -> dict:
    knowledge = knowledge or {}
    question_tokens = set(question.lower().replace("?", "").split())

    for key, value in knowledge.items():
        if not isinstance(value, dict):
            continue

        key_tokens = set(key.lower().replace("?", "").split())
        overlap = question_tokens & key_tokens
        if key.lower() in question.lower() or question.lower() in key.lower() or overlap:
            return {
                "status": "answered",
                "answer": value.get("answer", "Information unavailable."),
                "source_date": value.get("source_date", "unknown"),
                "confidence": value.get("confidence", 0.0),
            }

    return {
        "status": "escalate",
        "message": (
            "I couldn’t resolve this with the current knowledge base. "
            "A human RM has been notified."
        ),
    }
