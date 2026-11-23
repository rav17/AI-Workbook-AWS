"""Lambda handler: budgeting_calculator. Calculates budget allocations."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "user_id" in event else json.loads(event.get("body", "{}"))
    user_id = body.get("user_id", "")
    income = float(body.get("income", 0))
    target_savings_pct = float(body.get("target_savings_pct", 20.0))

    target_savings = income * (target_savings_pct / 100)
    result = {
        "user_id": user_id,
        "monthly_income": income,
        "target_savings": target_savings,
        "recommended_allocation": {
            "needs": income * 0.50,
            "wants": income * 0.30,
            "savings": target_savings,
        },
        "annual_savings_potential": target_savings * 12,
    }

    return {"statusCode": 200, "body": json.dumps(result)}
