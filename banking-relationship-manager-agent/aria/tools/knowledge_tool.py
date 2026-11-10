from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ProductAnswer:
    answer: str
    confidence: float
    source_date: str
    citations: list[str] | None = None


def extract_source_date(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(
        r"(?:as\s+of|source\s+date|dated)\s*[: ]\s*(\d{4}-\d{2}-\d{2})",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", str(text))
    if iso_match:
        return iso_match.group(1)
    return None


def format_citation(source: str | dict[str, Any] | None, answer: str | None = None) -> str:
    if isinstance(source, dict):
        source_label = str(source.get("source", "knowledge-base"))
        source_date = str(source.get("source_date") or extract_source_date(answer) or "unknown")
        if source_label:
            return f"{source_label} (updated {source_date})"
        return f"knowledge-base (updated {source_date})"
    if source:
        source_date = extract_source_date(str(source)) or "unknown"
        return f"{source} (updated {source_date})"
    return f"knowledge-base (updated {extract_source_date(answer) or 'unknown'})"


def _normalized_terms(value: str) -> set[str]:
    return {token for token in value.lower().replace("?", "").replace("-", " ").split() if token}


def _score_match(query: str, key: str, value: dict[str, Any]) -> tuple[int, float]:
    normalized_query = _normalized_terms(query)
    normalized_key = _normalized_terms(key)
    overlap = len(normalized_query & normalized_key)

    if query.lower() in key.lower() or key.lower() in query.lower():
        overlap += 2

    confidence = float(value.get("confidence", 0.0) or 0.0)
    return overlap, confidence


def query_product_info(query: str, knowledge: dict[str, Any] | None = None) -> ProductAnswer:
    knowledge = knowledge or {}

    best_match: tuple[int, float, str, dict[str, Any]] | None = None
    for key, value in knowledge.items():
        if not isinstance(value, dict):
            continue
        match_score = _score_match(query, key, value)
        if match_score[0] > 0:
            candidate = (match_score[0], match_score[1], key, value)
            if (
                best_match is None
                or candidate[0] > best_match[0]
                or (candidate[0] == best_match[0] and candidate[1] > best_match[1])
            ):
                best_match = candidate

    if best_match is None:
        raise ValueError("No relevant knowledge found for the requested product information.")

    _, confidence, _, best_value = best_match
    answer = str(best_value.get("answer", "Information unavailable."))
    source_date = str(best_value.get("source_date") or extract_source_date(answer) or "unknown")
    citations = [format_citation(best_value, answer)]
    return ProductAnswer(
        answer=answer,
        confidence=float(confidence),
        source_date=source_date,
        citations=citations,
    )


def answer_service_query(question: str, knowledge: dict[str, Any] | None = None) -> dict[str, Any]:
    knowledge = knowledge or {}
    question_tokens = _normalized_terms(question)
    rate_keywords = {"rate", "rates", "yield", "interest", "returns", "fixed", "deposit"}

    best_match: tuple[int, float, str, dict[str, Any]] | None = None
    for key, value in knowledge.items():
        if not isinstance(value, dict):
            continue

        overlap = len(question_tokens & _normalized_terms(key))
        if key.lower() in question.lower() or question.lower() in key.lower() or overlap:
            candidate = (overlap, float(value.get("confidence", 0.0) or 0.0), key, value)
            if (
                best_match is None
                or candidate[0] > best_match[0]
                or (candidate[0] == best_match[0] and candidate[1] > best_match[1])
            ):
                best_match = candidate

    if best_match is None:
        return {
            "status": "escalate",
            "message": (
                "I couldn’t resolve this with the current knowledge base. "
                "A human RM has been notified."
            ),
        }

    _, confidence, _, value = best_match
    source_date = value.get("source_date") or extract_source_date(str(value.get("answer", "")))
    is_rate_query = bool(question_tokens & rate_keywords)
    low_confidence = confidence < 0.7
    missing_source = is_rate_query and not source_date

    if low_confidence or missing_source:
        return {
            "status": "escalate",
            "message": (
                "The current answer is below confidence or missing the required "
                "source date; a human RM has been notified."
            ),
            "source_date": source_date or "unknown",
            "confidence": confidence,
            "citation": format_citation(value, value.get("answer")),
        }

    return {
        "status": "answered",
        "answer": value.get("answer", "Information unavailable."),
        "source_date": source_date or "unknown",
        "confidence": confidence,
        "citation": format_citation(value, value.get("answer")),
    }
