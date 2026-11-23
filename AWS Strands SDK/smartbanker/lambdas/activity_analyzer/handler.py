"""Lambda handler: activity_analyzer. Analyzes user banking activity metrics."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "user_id" in event else json.loads(event.get("body", "{}"))
    user_id = body.get("user_id", "")
    period_months = int(body.get("period_months", 6))

    # Production: integrate with banking analytics platform
    result = {
        "user_id": user_id,
        "period_months": period_months,
        "transaction_count": 45,
        "avg_monthly_balance": 25000.0,
        "salary_credits": 3,
        "investment_transactions": 2,
        "loan_inquiries": 1,
        "digital_channel_usage": 0.85,
        "branch_visits": 1,
        "services_used": ["checking", "savings", "debit_card", "online_banking"],
    }

    return {"statusCode": 200, "body": json.dumps(result)}
