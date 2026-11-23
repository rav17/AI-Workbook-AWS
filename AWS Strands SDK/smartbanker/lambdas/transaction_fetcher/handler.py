"""Lambda handler: transaction_fetcher. Retrieves user transaction data."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "user_id" in event else json.loads(event.get("body", "{}"))
    user_id = body.get("user_id", "")
    days = body.get("days", 30)

    # Production: integrate with core banking transaction API
    transactions = [
        {"date": "2025-07-15", "category": "groceries", "amount": 120.50, "merchant": "FreshMart"},
        {"date": "2025-07-14", "category": "dining", "amount": 45.00, "merchant": "Cafe Latte"},
        {"date": "2025-07-13", "category": "utilities", "amount": 200.00, "merchant": "PowerCo"},
        {"date": "2025-07-12", "category": "entertainment", "amount": 15.99, "merchant": "StreamFlix"},
        {"date": "2025-07-10", "category": "groceries", "amount": 89.30, "merchant": "FreshMart"},
        {"date": "2025-07-08", "category": "transport", "amount": 55.00, "merchant": "MetroPass"},
        {"date": "2025-07-05", "category": "shopping", "amount": 250.00, "merchant": "TechStore"},
    ]

    result = {
        "user_id": user_id,
        "days": days,
        "transactions": transactions,
        "total_spent": sum(t["amount"] for t in transactions),
    }

    return {"statusCode": 200, "body": json.dumps(result)}
