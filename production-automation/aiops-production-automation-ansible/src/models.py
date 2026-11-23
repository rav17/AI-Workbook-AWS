"""Data models, enums, and Pydantic validation models for the self-healing infrastructure system."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --- Enums ---


class Severity(Enum):
    """Internal severity levels mapped from Alertmanager severity labels."""

    P1 = "P1"  # critical
    P2 = "P2"  # warning
    P3 = "P3"  # info


class RemediationStatus(Enum):
    """Possible outcomes of a playbook execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


class AlertStatus(Enum):
    """Alert firing status."""

    FIRING = "firing"
    RESOLVED = "resolved"


# --- Dataclasses ---


@dataclass
class AlertmanagerAlert:
    """Single alert from Alertmanager payload."""

    status: str
    labels: dict[str, str]
    annotations: dict[str, str]
    starts_at: str
    ends_at: str
    generator_url: str = ""
    fingerprint: str = ""


@dataclass
class AlertmanagerPayload:
    """Full Alertmanager webhook payload."""

    version: str
    group_key: str
    status: str
    receiver: str
    alerts: list[AlertmanagerAlert]
    group_labels: dict[str, str] = field(default_factory=dict)
    common_labels: dict[str, str] = field(default_factory=dict)
    common_annotations: dict[str, str] = field(default_factory=dict)
    external_url: str = ""


@dataclass
class NormalizedAlert:
    """Standardized internal alert representation."""

    incident_id: str
    alert_name: str
    severity: Severity
    status: AlertStatus
    labels: dict[str, str]
    annotations: dict[str, str]
    starts_at: datetime
    ends_at: Optional[datetime]
    raw_fingerprint: str = ""


@dataclass
class AssetInfo:
    """Asset inventory entry."""

    hostname: str
    ip_address: str
    location: str
    service_name: str
    service_owner: str


@dataclass
class EnrichedAlert:
    """Alert enriched with asset context."""

    incident_id: str
    alert_name: str
    severity: Severity
    status: AlertStatus
    labels: dict[str, str]
    annotations: dict[str, str]
    starts_at: datetime
    ends_at: Optional[datetime]
    asset: Optional[AssetInfo] = None
    is_enriched: bool = False


@dataclass
class MappingRule:
    """A single playbook mapping rule."""

    name: str
    conditions: dict[str, str]  # attribute -> expected value
    playbook_path: str
    priority: int = 0


@dataclass
class PlaybookMatch:
    """Result of playbook matching."""

    rule_name: str
    playbook_path: str
    matched_attributes: int


@dataclass
class ExecutionResult:
    """Result of Ansible playbook execution."""

    status: RemediationStatus
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    playbook_path: str
    target_host: str


@dataclass
class AuditRecord:
    """Complete audit trail entry for an incident."""

    incident_id: str
    alert_name: str
    severity: str
    affected_host: str
    timestamp_received: datetime
    enrichment_data: Optional[dict]
    matched_playbook: Optional[str]
    execution_result: Optional[str]
    execution_duration: Optional[float]
    notification_status: str
    output_summary: str = ""

    def to_json_line(self) -> str:
        """Serialize this AuditRecord to a single line of valid JSON.

        Converts the record to a JSON string with no embedded newlines,
        suitable for JSON Lines format (one JSON object per line).
        """
        data = asdict(self)
        # Convert datetime to ISO format string for JSON serialization
        data["timestamp_received"] = self.timestamp_received.isoformat()
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "AuditRecord":
        """Deserialize an AuditRecord from a JSON string.

        Args:
            json_str: A JSON string representing an AuditRecord.

        Returns:
            An AuditRecord instance reconstructed from the JSON data.
        """
        data = json.loads(json_str)
        # Convert ISO format string back to datetime
        data["timestamp_received"] = datetime.fromisoformat(data["timestamp_received"])
        return cls(**data)


@dataclass
class HealthResponse:
    """Health check response."""

    status: str  # "healthy" or "degraded"
    uptime_seconds: float
    version: str
    dependencies: dict[str, str]  # component -> status


# --- Pydantic Models for Request/Response Validation ---


class AlertmanagerAlertModel(BaseModel):
    """Pydantic model for validating a single alert in the Alertmanager payload."""

    status: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str = Field(default="")
    endsAt: str = Field(default="")
    generatorURL: str = Field(default="")
    fingerprint: str = Field(default="")

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: dict[str, str]) -> dict[str, str]:
        """Ensure alertname and severity are present and non-empty in labels."""
        if not v.get("alertname"):
            raise ValueError("labels must contain a non-empty 'alertname' field")
        if not v.get("severity"):
            raise ValueError("labels must contain a non-empty 'severity' field")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Ensure status is non-empty."""
        if not v or not v.strip():
            raise ValueError("status must be non-empty")
        return v


class AlertmanagerPayloadModel(BaseModel):
    """Pydantic model for validating the full Alertmanager webhook payload."""

    version: str = Field(default="4")
    groupKey: str = Field(default="")
    status: str = Field(default="firing")
    receiver: str = Field(default="")
    alerts: list[AlertmanagerAlertModel] = Field(min_length=1)
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str = Field(default="")

    @field_validator("alerts")
    @classmethod
    def validate_alerts_non_empty(cls, v: list[AlertmanagerAlertModel]) -> list[AlertmanagerAlertModel]:
        """Ensure at least one alert is present."""
        if not v:
            raise ValueError("alerts must contain at least one alert")
        return v


class HealthResponseModel(BaseModel):
    """Pydantic model for the health check response."""

    status: str = Field(description="Service status: 'healthy' or 'degraded'")
    uptime_seconds: float = Field(description="Uptime in seconds since service start")
    version: str = Field(description="Service version string")
    dependencies: dict[str, str] = Field(
        description="Map of dependency name to status"
    )


class ErrorResponseModel(BaseModel):
    """Pydantic model for error responses."""

    error: str = Field(description="Error message describing the validation failure")
    detail: Optional[str] = Field(
        default=None, description="Additional detail about the error"
    )


class WebhookResponseModel(BaseModel):
    """Pydantic model for successful webhook response."""

    status: str = Field(default="accepted", description="Processing status")
    alerts_received: int = Field(description="Number of alerts received in the payload")
