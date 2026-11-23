"""Lambda handler: tier_pricing_engine. Calculates tier-specific preferential pricing."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "user_tier" in event else json.loads(event.get("body", "{}"))
    user_tier = body.get("user_tier", "basic")
    base_rate = float(body.get("base_rate", 10.0))

    discounts = {"basic": 0.0, "preferred": 0.25, "premium": 0.50, "ultra-premium": 0.75}
    discount = discounts.get(user_tier, 0.0)
    adjusted_rate = max(base_rate - discount, 0.0)

    result = {"user_tier": user_tier, "base_rate": base_rate, "discount": discount, "adjusted_rate": adjusted_rate}
    return {"statusCode": 200, "body": json.dumps(result)}
