"""Lambda handler: balance_checker. Checks current account balances."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "user_id" in event else json.loads(event.get("body", "{}"))
    user_id = body.get("user_id", "")

    # Production: integrate with core banking balance API
    result = {
        "user_id": user_id,
        "checking": 5420.00,
        "savings": 12800.00,
        "investment": 35000.00,
        "total": 53220.00,
    }

    return {"statusCode": 200, "body": json.dumps(result)}
