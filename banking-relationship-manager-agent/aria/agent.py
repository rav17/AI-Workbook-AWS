from __future__ import annotations

from aria.tools.crm_tool import update_client_profile
from aria.tools.risk_tool import get_risk_questionnaire


class AriaAgent:
    def handle_client_message(self, payload: dict, crm_store: dict) -> dict:
        client_id = payload.get("client_id", "unknown")
        name = payload.get("name", "there")
        message = payload.get("message", "")
        needs = payload.get("needs", [])
        risk_appetite = payload.get("risk_appetite")

        need_summary = ", ".join(needs) if needs else "your goals"
        greeting = (
            f"Hello {name}, I’m Aria. I can help with your financial needs: "
            f"{need_summary}."
        )

        if "market" in message.lower() and not risk_appetite:
            next_step = (
                "I need to complete the risk questionnaire before recommending "
                "a market-linked product."
            )
            questionnaire = get_risk_questionnaire()
            update_client_profile(client_id, {"name": name, "needs": needs})
            return {
                "greeting": greeting,
                "next_step": next_step,
                "questionnaire": questionnaire,
                "crm_store": crm_store,
            }

        update_client_profile(client_id, {"name": name, "needs": needs})
        return {
            "greeting": greeting,
            "next_step": "I can help you review the next best step for your profile.",
            "crm_store": crm_store,
        }

    def handle_market_disclosure(self, payload: dict) -> dict:
        disclosure = (
            "This market-linked product is subject to market risk, and there is no "
            "guarantee or promise of return. Please review the product documentation "
            "and consider your investment horizon before proceeding."
        )
        return {
            "client_id": payload.get("client_id", "unknown"),
            "name": payload.get("name", "Unknown"),
            "disclosure": disclosure,
        }

    def handle_wallet_profile(self, payload: dict) -> dict:
        assets = payload.get("external_assets", [])
        suggestion = (
            "Consolidating these external assets could improve visibility, reduce "
            "fragmentation, and unlock benefits without pressure."
        )
        return {
            "wallet_profile": {
                "client_id": payload.get("client_id", "unknown"),
                "external_assets": assets,
            },
            "suggestion": suggestion,
        }

    def recommend_products(self, payload: dict) -> dict:
        risk_appetite = payload.get("risk_appetite", "moderate")
        goal = payload.get("goal", "wealth management")
        balance = payload.get("balance", 0)

        recommendations = []
        if risk_appetite in {"moderate", "high"}:
            recommendations.append("Mutual fund SIPs aligned to your wealth-growth goal.")
        if balance >= 100000:
            recommendations.append(
                "Fixed deposit options with competitive rates for cash allocation."
            )
        recommendations.append(
            "Protected savings or premium banking benefits for balance management."
        )

        return {
            "goal": goal,
            "balance": balance,
            "recommendations": recommendations,
        }
