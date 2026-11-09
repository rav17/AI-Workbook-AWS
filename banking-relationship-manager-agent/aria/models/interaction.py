from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class FollowUpAction(BaseModel):
    action: str = Field(min_length=1)
    due_date: datetime | None = None
    assignee: str | None = None

    @field_validator("due_date")
    @classmethod
    def require_aware_due_date(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("follow-up due dates must include a timezone")
            return value.astimezone(UTC)
        return value


class InteractionSummary(BaseModel):
    client_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    topics_discussed: list[str] = Field(min_length=1)
    client_preferences: list[str] = Field(default_factory=list)
    follow_up_actions: list[FollowUpAction] = Field(default_factory=list)
    segment_flags: list[str] = Field(default_factory=list)
    interaction_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    escalation_id: str | None = None

    @field_validator("interaction_date")
    @classmethod
    def require_aware_interaction_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("interaction dates must include a timezone")
        return value.astimezone(UTC)
