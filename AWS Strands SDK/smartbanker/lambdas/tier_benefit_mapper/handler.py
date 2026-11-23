"""Lambda handler: tier_benefit_mapper. Maps tier benefits to user activity."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "user_tier" in event else json.loads(event.get("body", "{}"))
    user_tier = body.get("user_tier", "basic")

    # Production: integrate with tier management service
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
    benefits = tier_benefits.get(user_tier, tier_benefits["basic"])

    result = {"user_tier": user_tier, "benefits": benefits}
    return {"statusCode": 200, "body": json.dumps(result)}
