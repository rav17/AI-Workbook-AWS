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
