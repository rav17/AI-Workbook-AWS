from __future__ import annotations

from datetime import date, timedelta
import json
from typing import Any
from uuid import uuid4

from strands import Agent, tool

from aria.agents.aria.statement_explainer.models import StatementTransaction
from aria.agents.aria.statement_explainer.tools import (
    categorise_spend as _categorise_spend,
    compare_category_spend as _compare_category_spend,
    detect_anomalies as _detect_anomalies,
    explain_transaction as _explain_transaction,
    get_transactions as _get_transactions,
    summarise_period as _summarise_period,
)

_SPECIALIST_SYSTEM_PROMPT = (
    "You are Aria's account statement specialist. First call list_authorized_statements "
    "when no opaque statement reference is in the conversation. Use only the statement "
    "Gateway tools and evidence they return. Never infer account access or invent rows, "
    "amounts, or balances. If access is denied or evidence is insufficient, say so."
)
_GATEWAY_TOOL_PREFIX = "aria-statements___"
_GATEWAY_PAGE_SIZE = 25
_MAX_ANALYSIS_ROWS = 500


class StatementGatewayError(RuntimeError):
    pass


def should_route_statement_question(question: str) -> bool:
    normalized = (question or "").lower()
    terms = (
        "statement",
        "transaction",
        "balance",
        "debit",
        "credit",
        "salary",
        "utility",
        "standing order",
        "narrative",
        "category",
        "anomaly",
        "neft",
    )
    return bool(normalized) and any(term in normalized for term in terms)


def route_statement_question(question: str) -> dict[str, Any]:
    return {
        "should_route": should_route_statement_question(question),
        "reason": "statement-specific question",
    }


def _call_gateway(
    gateway_client: Any,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    result = gateway_client.call_tool_sync(
        str(uuid4()),
        f"{_GATEWAY_TOOL_PREFIX}{tool_name}",
        arguments,
        read_timeout_seconds=timedelta(seconds=20),
    )
    if not isinstance(result, dict) or result.get("status") != "success":
        raise StatementGatewayError("statement access is unavailable")

    payload = result.get("structuredContent")
    if not isinstance(payload, dict):
        content = result.get("content", [])
        text = next(
            (
                item.get("text")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ),
            None,
        )
        try:
            payload = json.loads(text) if isinstance(text, str) else None
        except json.JSONDecodeError as exc:
            raise StatementGatewayError("statement Gateway returned invalid data") from exc

    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise StatementGatewayError("statement access is unavailable")
    return payload


def _authorized_rows(
    gateway_client: Any,
    tenant_id: str,
    user_id: str,
    statement_ref: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    trans_id: str | None = None,
) -> list[StatementTransaction]:
    rows: list[StatementTransaction] = []
    page_token: str | None = None
    seen_tokens: set[str] = set()
    max_pages = (_MAX_ANALYSIS_ROWS // _GATEWAY_PAGE_SIZE) + 1

    for _ in range(max_pages):
        arguments: dict[str, Any] = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "statement_ref": statement_ref,
            "page_size": _GATEWAY_PAGE_SIZE,
        }
        if start_date:
            arguments["start_date"] = start_date
        if end_date:
            arguments["end_date"] = end_date
        if page_token:
            arguments["page_token"] = page_token
        if trans_id:
            arguments["trans_id"] = trans_id

        response = _call_gateway(
            gateway_client,
            "get_statement_transactions",
            arguments,
        )
        page = response.get("rows", [])
        if not isinstance(page, list):
            raise StatementGatewayError("statement Gateway returned invalid rows")
        rows.extend(StatementTransaction.model_validate(row) for row in page)
        if len(rows) > _MAX_ANALYSIS_ROWS:
            raise StatementGatewayError("statement analysis exceeded its row limit")

        next_token = response.get("next_page_token")
        if not next_token:
            return rows
        if not isinstance(next_token, str) or next_token in seen_tokens:
            raise StatementGatewayError("statement Gateway returned an invalid page token")
        seen_tokens.add(next_token)
        page_token = next_token

    raise StatementGatewayError("statement analysis exceeded its page limit")


def build_statement_explainer_tool(
    *,
    model: Any,
    gateway_client: Any,
    tenant_id: str,
    user_id: str,
) -> Any:
    if not tenant_id or not user_id:
        raise ValueError("verified tenant and user identity are required")

    @tool
    def list_authorized_statements() -> dict[str, Any]:
        """List only statements assigned to the authenticated relationship manager."""
        return _call_gateway(
            gateway_client,
            "list_authorized_statements",
            {"tenant_id": tenant_id, "user_id": user_id, "limit": 25},
        )

    @tool
    def get_transactions(
        statement_ref: str,
        start_date: str | None = None,
        end_date: str | None = None,
        dr_cr_ind: str | None = None,
        min_amount: str | None = None,
        narrative_keyword: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Search bounded transactions in one Gateway-authorized statement."""
        rows = _authorized_rows(
            gateway_client,
            tenant_id,
            user_id,
            statement_ref,
            start_date=start_date,
            end_date=end_date,
        )
        matches = _get_transactions(
            rows,
            start_date=start_date,
            end_date=end_date,
            dr_cr_ind=dr_cr_ind,
            min_amount=min_amount,
            narrative_keyword=narrative_keyword,
            category=category,
            max_results=25,
        )
        return {"rows": matches, "transaction_ids": [row["trans_id"] for row in matches]}

    @tool
    def summarise_period(statement_ref: str, start_date: str, end_date: str) -> dict[str, Any]:
        """Summarize an inclusive period using Gateway-authorized source rows."""
        rows = _authorized_rows(
            gateway_client,
            tenant_id,
            user_id,
            statement_ref,
            start_date=start_date,
            end_date=end_date,
        )
        return _summarise_period(rows, start_date, end_date)

    @tool
    def categorise_spend(
        statement_ref: str,
        start_date: str,
        end_date: str,
        prior_start_date: str | None = None,
        prior_end_date: str | None = None,
    ) -> dict[str, Any]:
        """Categorize current spending and optionally compare a prior period."""
        if (prior_start_date is None) != (prior_end_date is None):
            return {"status": "invalid_comparison_range"}
        rows = _authorized_rows(
            gateway_client,
            tenant_id,
            user_id,
            statement_ref,
            start_date=min(start_date, prior_start_date or start_date),
            end_date=max(end_date, prior_end_date or end_date),
        )
        result = _categorise_spend(rows, start_date, end_date)
        if prior_start_date and prior_end_date:
            result["comparison"] = _categorise_spend(rows, prior_start_date, prior_end_date)
            result["category_changes"] = {
                category: result["category_totals"].get(category, 0)
                - result["comparison"]["category_totals"].get(category, 0)
                for category in sorted(
                    set(result["category_totals"]) | set(result["comparison"]["category_totals"])
                )
            }
        return result

    @tool
    def detect_anomalies(
        statement_ref: str,
        category: str,
        current_start: str,
        current_end: str,
    ) -> dict[str, Any]:
        """Compare category spend with the preceding three complete calendar months."""
        current_date = date.fromisoformat(current_start)
        month_index = current_date.year * 12 + current_date.month - 1 - 3
        year, zero_month = divmod(month_index, 12)
        baseline_start = date(year, zero_month + 1, 1).isoformat()
        rows = _authorized_rows(
            gateway_client,
            tenant_id,
            user_id,
            statement_ref,
            start_date=baseline_start,
            end_date=current_end,
        )
        return _detect_anomalies(rows, category, current_start, current_end)

    @tool
    def explain_transaction(statement_ref: str, trans_id: str) -> dict[str, Any]:
        """Explain one transaction resolved through an authorized Gateway lookup."""
        rows = _authorized_rows(
            gateway_client,
            tenant_id,
            user_id,
            statement_ref,
            trans_id=trans_id,
        )
        return _explain_transaction(rows, trans_id)

    specialist = Agent(
        model=model,
        name="account_statement_explainer_specialist",
        description="Analyze only statements returned by Aria's authorized statement Gateway tools.",
        system_prompt=_SPECIALIST_SYSTEM_PROMPT,
        tools=[
            list_authorized_statements,
            get_transactions,
            summarise_period,
            categorise_spend,
            detect_anomalies,
            explain_transaction,
        ],
    )
    return specialist.as_tool(
        name="account_statement_explainer",
        description=(
            "Analyze an authorized statement using Gateway-backed reads and deterministic calculations."
        ),
        preserve_context=False,
    )
