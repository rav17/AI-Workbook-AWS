"""Lambda handler: service_request_processor. Processes banking service requests."""
import json


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "request_type" in event else json.loads(event.get("body", "{}"))
    request_type = body.get("request_type", "")
    description = body.get("description", "")
    user_id = body.get("user_id", "")

    # Production: integrate with core banking service request system
    result = {
        "request_type": request_type,
        "user_id": user_id,
        "status": "processed",
        "message": f"Service request '{request_type}' has been processed.",
    }

    return {"statusCode": 200, "body": json.dumps(result)}
