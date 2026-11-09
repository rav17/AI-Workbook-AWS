from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReinvestmentOption:
    name: str
    rate: str
    rationale: str


@dataclass
class MaturityEvent:
    client_id: str
    days_until_maturity: int
    amount: float
    status: str = "pending"
    recommended_action: str = "review_reinvestment"
    reinvestment_options: list[ReinvestmentOption] = field(default_factory=list)


@dataclass
class OutflowEvent:
    client_id: str
    amount: float
    threshold_amount: float
    event_type: str = "large_outflow"
    recommended_action: str = "rebalance_portfolio"
