from aria.config import get_settings
from aria.guardrails.processor import GuardrailProcessor
from aria.models.client import ClientProfile


def test_config_loads_defaults():
    settings = get_settings()

    assert settings.app_name == "aria"
    assert settings.environment in {"dev", "test", "prod"}
    assert settings.max_tool_calls > 0


def test_client_profile_serializes(sample_profile_payload):
    profile = ClientProfile.model_validate(sample_profile_payload)

    assert profile.client_id == "CUST-1001"
    assert profile.name == "Aisha Khan"
    assert profile.segment == "premier"
    assert "wealth growth" in profile.needs


def test_guardrail_processor_redacts_sensitive_content():
    processor = GuardrailProcessor()
    message = "My PIN is 1234 and OTP is 567890. Please help."

    redacted = processor.redact_sensitive_content(message)

    assert "1234" not in redacted
    assert "567890" not in redacted
    assert "PIN" in redacted or "otp" in redacted.lower()
