"""Centralized configuration with environment variable loading and defaults."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable configuration loaded from environment variables with sensible defaults."""

    # Runtime mode
    use_mocks: bool = field(default_factory=lambda: os.getenv("USE_MOCKS", "true").lower() == "true")

    # AWS
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    bedrock_model_id: str = field(
        default_factory=lambda: os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
    )

    # StormForce (Salesforce)
    stormforce_instance_url: str = field(
        default_factory=lambda: os.getenv("STORMFORCE_INSTANCE_URL", "https://stormforce.my.salesforce.com")
    )
    stormforce_client_id: str = field(default_factory=lambda: os.getenv("STORMFORCE_CLIENT_ID", ""))
    stormforce_client_secret: str = field(default_factory=lambda: os.getenv("STORMFORCE_CLIENT_SECRET", ""))

    # SMS (End User Messaging)
    sms_origination_identity: str = field(
        default_factory=lambda: os.getenv("SMS_ORIGINATION_IDENTITY", "")
    )

    # DynamoDB
    dynamodb_workflow_table: str = field(
        default_factory=lambda: os.getenv("DYNAMODB_WORKFLOW_TABLE", "mobilization-workflow-state")
    )
    dynamodb_conversation_table: str = field(
        default_factory=lambda: os.getenv("DYNAMODB_CONVERSATION_TABLE", "mobilization-conversation-history")
    )

    # CloudWatch
    cloudwatch_log_group: str = field(
        default_factory=lambda: os.getenv("CLOUDWATCH_LOG_GROUP", "/fpl/mobilization-confirmation-agent")
    )

    # Timezone
    default_timezone: str = field(default_factory=lambda: os.getenv("DEFAULT_TIMEZONE", "America/New_York"))

    # Agent behavior — configurable without code deploy (Appendix A)
    response_timer_minutes: int = 60
    escalation_timer_minutes: int = 60
    eta_validation_enabled: bool = field(default_factory=lambda: os.getenv("ETA_VALIDATION_ENABLED", "true").lower() == "true")
    eta_plausibility_threshold_percent: float = 25.0
    standard_travel_pace_mph: float = 55.0
    eta_monitoring_variance_hours: float = 1.0
    max_clarification_attempts: int = 3
    sms_max_segment_chars: int = 160
    conversation_ttl_days: int = 90
    followup_delay_options_minutes: list[int] = field(default_factory=lambda: [15, 30, 60])

    # Monitoring check-in (Reqs 21-28)
    checkin_interval_long_hours: int = 2
    checkin_interval_medium_minutes: int = 60
    checkin_interval_short_minutes: int = 30
    checkin_nonresponse_max: int = 3
    checkin_response_timer_minutes: int = 60
