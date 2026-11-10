from aria.workflow.validator import WorkflowValidator


def test_validator_allows_valid_profile_update():
    validator = WorkflowValidator()
    result = validator.validate(
        {
            "client_id": "CUST-1",
            "name": "Aisha",
            "risk_appetite": "moderate",
            "segment": "premier",
        }
    )

    assert result["valid"] is True


def test_validator_blocks_invalid_payload():
    validator = WorkflowValidator()
    result = validator.validate({"client_id": "", "segment": "premier"})

    assert result["valid"] is False
    assert result["errors"]


def test_validator_blocks_unauthorized_confirmation_and_compliance_failures():
    validator = WorkflowValidator()

    unauthorized = validator.validate_authorized_patch(
        {"client_id": "CUST-1"},
        {"risk_appetite": "moderate"},
        authorized_fields={"segment"},
    )
    assert unauthorized["reason_code"] == "unauthorized_field"

    confirmation = validator.validate_authorized_patch(
        {"client_id": "CUST-1"},
        {"segment": "premier"},
        authorized_fields={"segment"},
        requires_confirmation=True,
    )
    assert confirmation["reason_code"] == "confirmation_required"

    kyc = validator.validate_authorized_patch(
        {"client_id": "CUST-1", "kyc_status": "expired"},
        {"segment": "premier"},
        authorized_fields={"segment"},
    )
    assert kyc["reason_code"] == "kyc_required"

    aml = validator.validate_authorized_patch(
        {"client_id": "CUST-1", "kyc_status": "current", "aml_status": "flagged"},
        {"segment": "premier"},
        authorized_fields={"segment"},
    )
    assert aml["reason_code"] == "aml_review_required"
