"""Lambda handler: document_guidance_tool. Provides document guidance for banking operations."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "document_type" in event else json.loads(event.get("body", "{}"))
    document_type = body.get("document_type", "")
    user_id = body.get("user_id", "")

    # Production: integrate with document management system
    guidance = {
        "kyc_update": ["Government-issued photo ID", "Proof of address (utility bill or bank statement)", "PAN card"],
        "account_modification": ["Account holder identification", "Signed modification request form"],
        "loan_application": ["Income proof (salary slips or ITR)", "Address proof", "Bank statements (6 months)", "Photo ID"],
    }
    docs = guidance.get(document_type, ["Please contact support for document requirements."])

    result = {"document_type": document_type, "user_id": user_id, "required_documents": docs}
    return {"statusCode": 200, "body": json.dumps(result)}
