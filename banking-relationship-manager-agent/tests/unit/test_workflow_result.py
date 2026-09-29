from aria.workflow.result import WorkflowResult
from aria.workflow.validator import WorkflowValidator


def test_workflow_result_records_patch_outcome():
    result = WorkflowResult(
        valid=True,
        state={"client_id": "CUST-1", "risk_appetite": "moderate"},
        next_step="risk_questionnaire",
    )

    assert result.valid is True
    assert result.next_step == "risk_questionnaire"


def test_validator_rejects_locked_field_updates():
    validator = WorkflowValidator()
    validation = validator.validate_patch(
        {"client_id": "CUST-1", "workflow_version": 3},
        {"workflow_version": 2},
        locked_fields={"workflow_version"},
    )

    assert validation["valid"] is False
    assert "workflow_version" in " ".join(validation["errors"]).lower()
