"""Financial tools as Strands @tool functions.

Each tool has a dual execution path:
- USE_LAMBDA=true  → invokes the corresponding AWS Lambda via AgentCore Gateway
- USE_LAMBDA=false → runs the local stub implementation (dev/test mode)

Traces: R3, R4, R5, R6, R20, R28, R30, R32, R39.
"""
from strands import tool
import json

from tools.lambda_invoker import invoke_tool_lambda, is_lambda_enabled


# ---------------------------------------------------------------------------
# Helper: route to Lambda or local fallback
# ---------------------------------------------------------------------------

def _invoke_or_local(tool_name: str, payload: dict, local_fn) -> str:
    """Invoke Lambda if enabled, otherwise run local stub."""
    if is_lambda_enabled():
        result = invoke_tool_lambda(tool_name, payload)
        return json.dumps(result)
    return local_fn(payload)


# ===========================================================================
# Phase 1 Tools
# ===========================================================================


@tool
def transaction_fetcher(user_id: str, days: int = 30) -> str:
    """Retrieves user transaction data for spending analysis.

    Args:
        user_id: The user identifier.
        days: Number of days of history to fetch (default 30).

    Returns:
        JSON string of transaction data.
    """
    payload = {"user_id": user_id, "days": days}

    def _local(p):
        transactions = [
            {"date": "2025-07-15", "category": "groceries", "amount": 120.50, "merchant": "FreshMart"},
            {"date": "2025-07-14", "category": "dining", "amount": 45.00, "merchant": "Cafe Latte"},
            {"date": "2025-07-13", "category": "utilities", "amount": 200.00, "merchant": "PowerCo"},
            {"date": "2025-07-12", "category": "entertainment", "amount": 15.99, "merchant": "StreamFlix"},
            {"date": "2025-07-10", "category": "groceries", "amount": 89.30, "merchant": "FreshMart"},
            {"date": "2025-07-08", "category": "transport", "amount": 55.00, "merchant": "MetroPass"},
            {"date": "2025-07-05", "category": "shopping", "amount": 250.00, "merchant": "TechStore"},
        ]
        return json.dumps({"user_id": p["user_id"], "days": p["days"], "transactions": transactions, "total_spent": sum(t["amount"] for t in transactions)})

    return _invoke_or_local("transaction_fetcher", payload, _local)


@tool
def balance_checker(user_id: str) -> str:
    """Checks current account balances for savings analysis.

    Args:
        user_id: The user identifier.

    Returns:
        JSON string of account balances.
    """
    payload = {"user_id": user_id}

    def _local(p):
        return json.dumps({"user_id": p["user_id"], "checking": 5420.00, "savings": 12800.00, "investment": 35000.00, "total": 53220.00})

    return _invoke_or_local("balance_checker", payload, _local)


@tool
def investment_data_api(query: str, risk_tolerance: str = "medium") -> str:
    """Retrieves market and investment data for investment advisory.

    Args:
        query: The investment query or asset class to research.
        risk_tolerance: User risk tolerance level (low, medium, high).

    Returns:
        JSON string of investment data and options.
    """
    payload = {"query": query, "risk_tolerance": risk_tolerance}

    def _local(p):
        options = {
            "low": [
                {"name": "Treasury Bonds ETF", "expected_return": "4-5%", "risk": "low", "type": "fixed_income"},
                {"name": "High-Grade Corporate Bonds", "expected_return": "5-6%", "risk": "low", "type": "fixed_income"},
            ],
            "medium": [
                {"name": "S&P 500 Index Fund", "expected_return": "8-10%", "risk": "medium", "type": "equity"},
                {"name": "Balanced Fund", "expected_return": "6-8%", "risk": "medium", "type": "balanced"},
            ],
            "high": [
                {"name": "Growth Tech ETF", "expected_return": "12-18%", "risk": "high", "type": "equity"},
                {"name": "Emerging Markets Fund", "expected_return": "10-15%", "risk": "high", "type": "equity"},
            ],
        }
        return json.dumps({"query": p["query"], "risk_tolerance": p["risk_tolerance"], "options": options.get(p["risk_tolerance"], options["medium"])})

    return _invoke_or_local("investment_data_api", payload, _local)


@tool
def budgeting_calculator(user_id: str, income: float, target_savings_pct: float = 20.0) -> str:
    """Calculates budget allocations and savings potential.

    Args:
        user_id: The user identifier.
        income: Monthly income amount.
        target_savings_pct: Target savings percentage (default 20%).

    Returns:
        JSON string of budget breakdown.
    """
    payload = {"user_id": user_id, "income": income, "target_savings_pct": target_savings_pct}

    def _local(p):
        inc = p["income"]
        pct = p["target_savings_pct"]
        target = inc * (pct / 100)
        return json.dumps({"user_id": p["user_id"], "monthly_income": inc, "target_savings": target, "recommended_allocation": {"needs": inc * 0.50, "wants": inc * 0.30, "savings": target}, "annual_savings_potential": target * 12})

    return _invoke_or_local("budgeting_calculator", payload, _local)


# ===========================================================================
# Phase 2 Tools
# ===========================================================================


@tool
def service_request_processor(request_type: str, description: str, user_id: str = "") -> str:
    """Processes a routine banking service request.

    Args:
        request_type: Type of service request.
        description: Description of the request.
        user_id: The user identifier.

    Returns:
        JSON string with processing result.
    """
    payload = {"request_type": request_type, "description": description, "user_id": user_id}

    def _local(p):
        return json.dumps({"request_type": p["request_type"], "user_id": p["user_id"], "status": "processed", "message": f"Service request '{p['request_type']}' has been processed."})

    return _invoke_or_local("service_request_processor", payload, _local)


@tool
def escalation_tracker(request_id: str, reason: str = "") -> str:
    """Tracks escalation of a service request to higher-level support.

    Args:
        request_id: The service request identifier.
        reason: Reason for escalation.

    Returns:
        JSON string with escalation tracking details.
    """
    payload = {"request_id": request_id, "reason": reason}

    def _local(p):
        import uuid as _uuid
        return json.dumps({"request_id": p["request_id"], "tracking_reference": f"ESC-{_uuid.uuid4().hex[:8].upper()}", "status": "escalated", "reason": p["reason"], "estimated_timeline": "3-5 business days"})

    return _invoke_or_local("escalation_tracker", payload, _local)


@tool
def document_guidance_tool(document_type: str, user_id: str = "") -> str:
    """Provides guidance on required documents for banking operations.

    Args:
        document_type: Type of document or operation requiring documentation.
        user_id: The user identifier.

    Returns:
        JSON string with document guidance.
    """
    payload = {"document_type": document_type, "user_id": user_id}

    def _local(p):
        guidance = {
            "kyc_update": ["Government-issued photo ID", "Proof of address (utility bill or bank statement)", "PAN card"],
            "account_modification": ["Account holder identification", "Signed modification request form"],
            "loan_application": ["Income proof (salary slips or ITR)", "Address proof", "Bank statements (6 months)", "Photo ID"],
        }
        docs = guidance.get(p["document_type"], ["Please contact support for document requirements."])
        return json.dumps({"document_type": p["document_type"], "user_id": p["user_id"], "required_documents": docs})

    return _invoke_or_local("document_guidance_tool", payload, _local)


@tool
def loan_product_catalog(loan_type: str = "personal_loan", user_tier: str = "basic") -> str:
    """Retrieves available loan products from the bank's product catalog.

    Args:
        loan_type: Type of loan.
        user_tier: User's programme tier for filtering eligible products.

    Returns:
        JSON string of available loan products.
    """
    payload = {"loan_type": loan_type, "user_tier": user_tier}

    def _local(p):
        catalog = {
            "personal_loan": {"name": "Personal Loan", "rate_range": "10.5%-16%", "max_amount": 2500000, "tenure": "1-5 years"},
            "auto_loan": {"name": "Auto Loan", "rate_range": "8.5%-12%", "max_amount": 5000000, "tenure": "1-7 years"},
            "property_backed_loan": {"name": "Property-Backed Loan", "rate_range": "8%-10.5%", "max_amount": 50000000, "tenure": "5-30 years"},
            "working_capital_facility": {"name": "Working Capital Facility", "rate_range": "11%-15%", "max_amount": 10000000, "tenure": "1-3 years"},
        }
        product = catalog.get(p["loan_type"], catalog["personal_loan"])
        return json.dumps({"loan_type": p["loan_type"], "user_tier": p["user_tier"], "product": product})

    return _invoke_or_local("loan_product_catalog", payload, _local)


@tool
def tier_pricing_engine(user_tier: str, base_rate: float = 10.0) -> str:
    """Calculates tier-specific preferential pricing for loan products.

    Args:
        user_tier: User's programme tier.
        base_rate: Base interest rate percentage.

    Returns:
        JSON string with tier-adjusted pricing.
    """
    payload = {"user_tier": user_tier, "base_rate": base_rate}

    def _local(p):
        discounts = {"basic": 0.0, "preferred": 0.25, "premium": 0.50, "ultra-premium": 0.75}
        discount = discounts.get(p["user_tier"], 0.0)
        adjusted = max(p["base_rate"] - discount, 0.0)
        return json.dumps({"user_tier": p["user_tier"], "base_rate": p["base_rate"], "discount": discount, "adjusted_rate": adjusted})

    return _invoke_or_local("tier_pricing_engine", payload, _local)


@tool
def activity_analyzer(user_id: str, period_months: int = 6) -> str:
    """Analyzes user banking activity metrics for value assessment.

    Args:
        user_id: The user identifier.
        period_months: Number of months of activity to analyze (default 6).

    Returns:
        JSON string with activity metrics.
    """
    payload = {"user_id": user_id, "period_months": period_months}

    def _local(p):
        return json.dumps({"user_id": p["user_id"], "period_months": p["period_months"], "transaction_count": 45, "avg_monthly_balance": 25000.0, "salary_credits": 3, "investment_transactions": 2, "loan_inquiries": 1, "digital_channel_usage": 0.85, "branch_visits": 1, "services_used": ["checking", "savings", "debit_card", "online_banking"]})

    return _invoke_or_local("activity_analyzer", payload, _local)


@tool
def tier_benefit_mapper(user_tier: str) -> str:
    """Maps tier benefits to user activity for value assessment.

    Args:
        user_tier: The user's current programme tier.

    Returns:
        JSON string with tier benefits and their descriptions.
    """
    payload = {"user_tier": user_tier}

    def _local(p):
        tier_benefits = {
            "basic": [
                {"benefit": "standard_checking", "description": "Basic checking account"},
                {"benefit": "debit_card", "description": "Standard debit card"},
                {"benefit": "online_banking", "description": "Online banking access"},
            ],
            "preferred": [
                {"benefit": "standard_checking", "description": "Basic checking account"},
                {"benefit": "debit_card", "description": "Standard debit card"},
                {"benefit": "online_banking", "description": "Online banking access"},
                {"benefit": "reduced_fees", "description": "Reduced transaction fees"},
                {"benefit": "priority_support", "description": "Priority customer support"},
            ],
            "premium": [
                {"benefit": "standard_checking", "description": "Basic checking account"},
                {"benefit": "debit_card", "description": "Premium debit card"},
                {"benefit": "online_banking", "description": "Online banking access"},
                {"benefit": "reduced_fees", "description": "Waived transaction fees"},
                {"benefit": "priority_support", "description": "Dedicated support line"},
                {"benefit": "lounge_access", "description": "Airport lounge access"},
                {"benefit": "wealth_advisory", "description": "Wealth management advisory"},
                {"benefit": "preferential_rates", "description": "Preferential loan/forex rates"},
            ],
            "ultra-premium": [
                {"benefit": "standard_checking", "description": "Basic checking account"},
                {"benefit": "debit_card", "description": "Ultra-premium debit card"},
                {"benefit": "online_banking", "description": "Online banking access"},
                {"benefit": "reduced_fees", "description": "All fees waived"},
                {"benefit": "priority_support", "description": "Dedicated relationship manager"},
                {"benefit": "lounge_access", "description": "Unlimited lounge access"},
                {"benefit": "wealth_advisory", "description": "Dedicated wealth management"},
                {"benefit": "preferential_rates", "description": "Best-in-class rates"},
                {"benefit": "concierge", "description": "Concierge services"},
                {"benefit": "insurance_coverage", "description": "Complimentary insurance"},
            ],
        }
        benefits = tier_benefits.get(p["user_tier"], tier_benefits["basic"])
        return json.dumps({"user_tier": p["user_tier"], "benefits": benefits})

    return _invoke_or_local("tier_benefit_mapper", payload, _local)
