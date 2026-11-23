"""Lambda handler: compliance_rule_checker. Validates requests against compliance rules."""
import json


MANDATORY_CHECKS = ["kyc_verification", "credit_check", "aml_screening", "sanctions_check"]
NON_WAIVABLE_RULES = ["kyc", "credit_assessment", "regulatory_compliance"]


def handler(event, context):
    """AWS Lambda entry point. Exposed via AgentCore Gateway."""
    body = event if isinstance(event, dict) and "request_context" in event else json.loads(event.get("body", "{}"))
    request_context = body.get("request_context", "")
    rule_set = body.get("rule_set", "default")

    # Production: integrate with compliance engine
    violations = []
    request_lower = request_context.lower()
    for rule in NON_WAIVABLE_RULES:
        if f"skip {rule}" in request_lower or f"bypass {rule}" in request_lower:
            violations.append(f"Cannot bypass mandatory rule: {rule}")

    result = {
        "request_context": request_context,
        "rule_set": rule_set,
        "compliant": len(violations) == 0,
        "violations": violations,
        "checks_performed": MANDATORY_CHECKS,
    }

    return {"statusCode": 200, "body": json.dumps(result)}
