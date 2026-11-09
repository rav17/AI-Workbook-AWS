from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConsolidationOpportunity:
    asset_type: str
    institution: str
    value: float
    benefit: str


@dataclass
class WalletProfile:
    client_id: str
    external_fds: list[dict[str, Any]] = field(default_factory=list)
    external_demat: list[dict[str, Any]] = field(default_factory=list)
    external_insurance: list[dict[str, Any]] = field(default_factory=list)
    estimated_external_assets: float = 0.0
    consolidation_opportunities: list[ConsolidationOpportunity] = field(default_factory=list)
    last_updated: str | None = None

    @classmethod
    def from_payload(cls, client_id: str, payload: dict[str, Any]) -> WalletProfile:
        external_assets = payload.get("external_assets", []) or []
        fds = []
        demat = []
        insurance = []
        total = 0.0
        opportunities = []

        for asset in external_assets:
            if not isinstance(asset, dict):
                continue
            asset_type = str(asset.get("type", "other")).lower()
            institution = str(asset.get("institution", "unknown"))
            value = float(asset.get("value", 0) or 0)
            total += value

            if "fd" in asset_type or "fixed" in asset_type or "deposit" in asset_type:
                fds.append({"type": asset_type, "institution": institution, "value": value})
                opportunities.append(
                    ConsolidationOpportunity(
                        asset_type="fixed_deposit",
                        institution=institution,
                        value=value,
                        benefit=(
                            "Transfer this deposit to the bank to centralize higher-"
                            "yield options and improve visibility without pressure."
                        ),
                    )
                )
            elif "demat" in asset_type or "equity" in asset_type or "investment" in asset_type:
                demat.append({"type": asset_type, "institution": institution, "value": value})
                opportunities.append(
                    ConsolidationOpportunity(
                        asset_type="demat",
                        institution=institution,
                        value=value,
                        benefit=(
                            "Bring this portfolio into the bank to unify reporting, "
                            "better manage risk, and simplify account servicing."
                        ),
                    )
                )
            elif "insurance" in asset_type:
                insurance.append({"type": asset_type, "institution": institution, "value": value})

        return cls(
            client_id=client_id,
            external_fds=fds,
            external_demat=demat,
            external_insurance=insurance,
            estimated_external_assets=total,
            consolidation_opportunities=opportunities,
            last_updated=payload.get("updated_at") or payload.get("last_updated"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "external_fds": self.external_fds,
            "external_demat": self.external_demat,
            "external_insurance": self.external_insurance,
            "estimated_external_assets": self.estimated_external_assets,
            "consolidation_opportunities": [
                {
                    "asset_type": item.asset_type,
                    "institution": item.institution,
                    "value": item.value,
                    "benefit": item.benefit,
                }
                for item in self.consolidation_opportunities
            ],
            "last_updated": self.last_updated,
        }
