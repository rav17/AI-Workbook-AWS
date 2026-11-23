"""Lambda handler: investment_data_api. Retrieves market and investment data."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "query" in event else json.loads(event.get("body", "{}"))
    query = body.get("query", "")
    risk_tolerance = body.get("risk_tolerance", "medium")

    # Production: integrate with market data provider API
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

    result = {
        "query": query,
        "risk_tolerance": risk_tolerance,
        "options": options.get(risk_tolerance, options["medium"]),
    }

    return {"statusCode": 200, "body": json.dumps(result)}
