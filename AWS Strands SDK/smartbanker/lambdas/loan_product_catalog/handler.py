"""Lambda handler: loan_product_catalog. Retrieves loan products from bank catalog."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "loan_type" in event else json.loads(event.get("body", "{}"))
    loan_type = body.get("loan_type", "personal_loan")
    user_tier = body.get("user_tier", "basic")

    # Production: integrate with product catalog service
    catalog = {
        "personal_loan": {"name": "Personal Loan", "rate_range": "10.5%-16%", "max_amount": 2500000, "tenure": "1-5 years"},
        "auto_loan": {"name": "Auto Loan", "rate_range": "8.5%-12%", "max_amount": 5000000, "tenure": "1-7 years"},
        "property_backed_loan": {"name": "Property-Backed Loan", "rate_range": "8%-10.5%", "max_amount": 50000000, "tenure": "5-30 years"},
        "working_capital_facility": {"name": "Working Capital Facility", "rate_range": "11%-15%", "max_amount": 10000000, "tenure": "1-3 years"},
    }
    product = catalog.get(loan_type, catalog["personal_loan"])

    result = {"loan_type": loan_type, "user_tier": user_tier, "product": product}
    return {"statusCode": 200, "body": json.dumps(result)}
