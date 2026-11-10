import pytest
from strands.models import BedrockModel

from aria.agents.aria.kyc_aml import ComplianceVerifier, build_kyc_aml_subagent_tool


def test_child_tool_schema_does_not_allow_model_to_select_subject():
    verifier = ComplianceVerifier(
        document_extractor=None,
        identity_verifier=None,
        policy_provider=None,
        aml_provider=None,
    )
    child_tool = build_kyc_aml_subagent_tool(
        model=BedrockModel(model_id="amazon.nova-lite-v1:0", region_name="us-east-1"),
        verified_subject_id="parent-verified-subject",
        verifier=verifier,
    )

    assert child_tool.tool_name == "kyc_aml_verification"
    schema = child_tool.tool_spec["inputSchema"]["json"]
    assert set(schema["properties"]) == {"input"}
    assert schema["required"] == ["input"]


def test_child_tool_builder_requires_parent_verified_subject():
    verifier = ComplianceVerifier(
        document_extractor=None,
        identity_verifier=None,
        policy_provider=None,
        aml_provider=None,
    )

    with pytest.raises(ValueError, match="parent-verified subject"):
        build_kyc_aml_subagent_tool(
            model=BedrockModel(model_id="amazon.nova-lite-v1:0", region_name="us-east-1"),
            verified_subject_id="",
            verifier=verifier,
        )
