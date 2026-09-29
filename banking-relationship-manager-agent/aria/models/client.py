from __future__ import annotations

from pydantic import BaseModel, Field


class ClientProfile(BaseModel):
    client_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    segment: str = Field(default="retail")
    risk_appetite: str | None = None
    needs: list[str] = Field(default_factory=list)
