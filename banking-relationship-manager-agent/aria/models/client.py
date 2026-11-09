from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClientProfile(BaseModel):
    client_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    segment: str = Field(default="retail")
    segment_flags: list[str] = Field(default_factory=list)
    risk_appetite: str | None = None
    family_members: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    wallet_profile: dict[str, Any] | None = None
    kyc_status: str = Field(default="missing")
    preferences: list[str] = Field(default_factory=list)
