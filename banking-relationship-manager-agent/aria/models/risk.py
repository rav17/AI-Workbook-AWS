from __future__ import annotations

from pydantic import BaseModel, Field


class RiskProfile(BaseModel):
    client_id: str = Field(..., min_length=1)
    risk_appetite: str = Field(default="moderate")
    risk_tolerance: int = Field(default=5, ge=0, le=10)
    investment_horizon_years: int | None = Field(default=None, ge=1)
    market_risk_acknowledged: bool = False
