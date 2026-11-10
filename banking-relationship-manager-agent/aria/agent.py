from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aria.agents.aria.statement_explainer.models import StatementAnalysisRequest
from aria.guardrails.processor import GuardrailProcessor
from aria.observability import Observability
from aria.tools.compliance_tool import KYCStatusProvider, check_kyc_status
from aria.tools.crm_tool import (
    create_followup_reminder,
    get_client_profile,
    log_interaction,
    update_client_profile,
)
from aria.tools.escalation_tool import escalate_request
from aria.tools.knowledge_tool import answer_service_query, query_product_info
from aria.tools.maturity_tool import (
    check_upcoming_maturities,
    detect_large_outflows,
    evaluate_maturity_event,
    evaluate_outflow_event,
)
from aria.tools.risk_tool import get_risk_questionnaire


class AriaAgent:
    def __init__(
        self,
        kyc_status_provider: KYCStatusProvider | None = None,
        knowledge_provider: Callable[[str], dict[str, Any]] | None = None,
        statement_tool: Callable[..., Any] | None = None,
    ) -> None:
        self._observability = Observability()
        self._kyc_status_provider = kyc_status_provider
        self._knowledge_provider = knowledge_provider
        self._statement_tool = statement_tool
        self._tools: dict[str, Callable[..., Any]] = {
            "handle_client_message": self.handle_client_message,
            "handle_market_disclosure": self.handle_market_disclosure,
            "handle_wallet_profile": self.handle_wallet_profile,
            "recommend_products": self.recommend_products,
            "read_client_profile": get_client_profile,
            "update_client_profile": update_client_profile,
            "log_interaction": log_interaction,
            "create_followup_reminder": create_followup_reminder,
            "query_product_info": query_product_info,
            "answer_service_query": answer_service_query,
            "get_risk_questionnaire": get_risk_questionnaire,
            "check_upcoming_maturities": check_upcoming_maturities,
            "detect_large_outflows": detect_large_outflows,
            "evaluate_maturity_event": evaluate_maturity_event,
            "evaluate_outflow_event": evaluate_outflow_event,
            "check_kyc_status": check_kyc_status,
            "escalate_request": escalate_request,
        }
        if statement_tool is not None:
            self._tools["account_statement_explainer"] = statement_tool

    def _verified_kyc_status(self, client_id: str) -> str | None:
        if self._kyc_status_provider is None or not client_id:
            return None
        try:
            status = self._kyc_status_provider(client_id)
        except Exception:
            self._observability.emit_operation(
                "compliance.kyc",
                {"provider_error": True},
                status="error",
            )
            return None
        if not isinstance(status, str) or status.strip().lower() not in {
            "current",
            "pending",
            "missing",
            "expired",
        }:
            self._observability.emit_operation(
                "compliance.kyc",
                {"provider_invalid_response": True},
                status="error",
            )
            return None
        return status.strip().lower()

    def registered_tools(self) -> list[str]:
        return sorted(self._tools)

    def build_runtime_agent(
        self,
        *,
        agent_id: str,
        session_id: str,
        model_id: str,
        region_name: str,
        session_dir: str,
        system_prompt: str | None = None,
        tools: list[object] | None = None,
    ) -> Any:
        from aria.framework.strands_runtime import build_strands_agent

        return build_strands_agent(
            agent_id=agent_id,
            session_id=session_id,
            model_id=model_id,
            region_name=region_name,
            session_dir=session_dir,
            system_prompt=system_prompt,
            tools=tools,
        )

    def execute_tool(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        arguments = dict(payload or {})
        try:
            if name == "handle_client_message":
                crm_store = arguments.pop("crm_store", {})
                result = tool(arguments, crm_store)
            elif name in {
                "handle_market_disclosure",
                "handle_wallet_profile",
                "recommend_products",
            }:
                result = tool(arguments)
            elif name in {
                "read_client_profile",
                "check_upcoming_maturities",
                "detect_large_outflows",
            }:
                client_id = str(arguments.pop("client_id", "unknown"))
                result = tool(client_id, **arguments)
            else:
                result = tool(**arguments)
        except Exception:
            self._observability.emit_operation(
                f"tool.{name}",
                {"client_id": arguments.get("client_id", "unknown")},
                status="error",
            )
            raise

        self._observability.emit_operation(
            f"tool.{name}",
            {"client_id": arguments.get("client_id", "unknown")},
        )
        return result

    def _family_summary(self, family_members: list[str] | tuple[str, ...] | None) -> str:
        members = family_members or []
        if not members:
            return ""
        return "family accounts for " + ", ".join(str(member) for member in members[:3])

    @staticmethod
    def _is_service_query(message: str) -> bool:
        normalized = message.lower().strip()
        query_starts = (
            "how do i",
            "how can i",
            "what is",
            "what are",
            "where can i",
            "when is",
            "can i ",
            "do i need",
        )
        query_terms = (" fee", " rate", " charge", " wire", " transfer", " document")
        return normalized.startswith(query_starts) or any(
            term in f" {normalized}" for term in query_terms
        )

    @staticmethod
    def _is_statement_query(message: str) -> bool:
        normalized = (message or "").lower().strip()
        if not normalized:
            return False
        statement_terms = (
            "statement",
            "transaction",
            "balance",
            "debit",
            "credit",
            "salary",
            "utility",
            "standing order",
            "narrative",
            "category",
            "anomaly",
            "neft",
        )
        return any(term in normalized for term in statement_terms)

    def _route_service_query(
        self,
        payload: dict[str, Any],
        *,
        client_id: str,
        name: str,
        profile: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        guarded = GuardrailProcessor().process_input(message)
        if guarded.blocked:
            return {
                "service_query": {
                    "status": "blocked",
                    "message": "Please remove sensitive or unsafe content and try again.",
                }
            }

        try:
            knowledge = (
                self._knowledge_provider(guarded.sanitized_message)
                if self._knowledge_provider
                else {}
            )
        except Exception:
            knowledge = {}
        service_query = answer_service_query(guarded.sanitized_message, knowledge)
        result: dict[str, Any] = {"service_query": service_query}
        if service_query.get("status") == "escalate":
            result["escalation"] = escalate_request(
                "unresolved query",
                {
                    "client_id": client_id,
                    "name": name,
                    "session_id": payload.get("session_id"),
                    "segment_flags": profile.get("segment_flags", []),
                    "question": guarded.sanitized_message,
                },
            )
        return result

    def handle_client_message(
        self, payload: dict[str, Any], crm_store: dict[str, Any]
    ) -> dict[str, Any]:
        client_id = payload.get("client_id", "unknown")
        name = payload.get("name", "there")
        message = payload.get("message", "")
        needs = payload.get("needs", [])
        risk_appetite = payload.get("risk_appetite")
        family_members = payload.get("family_members") or payload.get("family_accounts") or []

        need_summary = ", ".join(needs) if needs else "your goals"
        greeting = f"Hello {name}, I’m Aria. I can help with your financial needs: {need_summary}."

        kyc_status = self._verified_kyc_status(str(client_id))
        kyc_result = check_kyc_status(kyc_status)

        profile = update_client_profile(
            client_id,
            {
                "name": name,
                "needs": needs,
                "family_members": family_members,
                "risk_appetite": risk_appetite,
            },
        )
        if isinstance(crm_store, dict):
            crm_store[client_id] = profile

        family_ctg = self._family_summary(family_members)
        response: dict[str, object] = {
            "greeting": greeting,
            "tone": f"Aria is happy to help, {name}.",
            "next_step": "I can help you review the next best step for your profile.",
            "next_steps": [
                "- Confirm your current priorities and preferred time horizon.",
                "- Review suitable options after profile and eligibility checks.",
            ],
            "crm_store": crm_store,
            "requires_kyc": bool(kyc_result.get("requires_kyc", False)),
        }

        if kyc_result.get("requires_kyc"):
            response["next_step"] = (
                "I can help you review the next best step, but KYC must be current "
                "before new product requests can proceed."
            )

        if family_ctg:
            response["ctg_suggestion"] = (
                "Consider a family CTG review for your eligible family accounts and "
                "household goals."
            )
            response["next_step"] = (
                "I can help you review the next best step for your profile and "
                "family CTG opportunities."
            )
            response["next_steps"] = [
                "- Review your household goals and eligible family accounts.",
                "- Discuss CTG enrollment and shared banking benefits.",
            ]

        if "market" in message.lower() and not risk_appetite:
            next_step = (
                "I need to complete the risk questionnaire before recommending "
                "a market-linked product."
            )
            questionnaire = get_risk_questionnaire()
            response.update(
                {
                    "next_step": next_step,
                    "next_steps": [
                        "- Complete the structured risk questionnaire.",
                        "- Review market-linked options with the required disclosure.",
                    ],
                    "questionnaire": questionnaire,
                }
            )
            if family_ctg:
                response["ctg_suggestion"] = (
                    "Consider a family CTG review while we complete the risk "
                    "questionnaire for your household."
                )

        if self._is_service_query(message):
            response.update(
                self._route_service_query(
                    payload,
                    client_id=str(client_id),
                    name=str(name),
                    profile=profile,
                    message=message,
                )
            )
            service_query_result = response.get("service_query")
            if (
                isinstance(service_query_result, dict)
                and service_query_result.get("status") == "escalate"
            ):
                response["next_step"] = str(service_query_result["message"])

        if self._statement_tool is not None and self._is_statement_query(message):
            guarded = GuardrailProcessor().process_input(message)
            if guarded.blocked:
                response["statement_explainer"] = {
                    "status": "blocked",
                    "answer": "Please remove sensitive or unsafe content and try again.",
                }
            else:
                try:
                    request = StatementAnalysisRequest(
                        statement_ref=(
                            str(payload["statement_ref"])
                            if payload.get("statement_ref") is not None
                            else None
                        ),
                        question=guarded.sanitized_message,
                        session_context=str(payload.get("session_context") or "")[:400],
                    )
                    statement_result = self._statement_tool(
                        request.question,
                        statement_ref=request.statement_ref,
                        session_context=request.session_context,
                    )
                    if not isinstance(statement_result, dict):
                        raise ValueError("statement specialist returned an invalid result")
                    answer = statement_result.get("answer")
                    if isinstance(answer, str):
                        output = GuardrailProcessor().process_output(answer)
                        if output.blocked:
                            statement_result = {
                                "status": "blocked",
                                "answer": (
                                    "I can't provide that response. Please contact your "
                                    "relationship manager."
                                ),
                            }
                        else:
                            statement_result = {
                                **statement_result,
                                "answer": output.sanitized_message,
                            }
                    response["statement_explainer"] = statement_result
                except Exception:
                    response["statement_explainer"] = {
                        "status": "error",
                        "answer": (
                            "I couldn't safely analyze the selected synthetic statement. "
                            "Please try again."
                        ),
                    }
            response["next_step"] = (
                "I’ve routed this to the statement specialist for a transaction-grounded review."
            )

        return response

    def handle_market_disclosure(self, payload: dict[str, Any]) -> dict[str, Any]:
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

    def handle_wallet_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        assets = payload.get("external_assets", []) or []
        normalized: list[str | dict[str, Any]] = []
        estimated_total = 0.0
        for asset in assets:
            if isinstance(asset, str):
                normalized.append(asset)
                digits = "".join(ch for ch in asset if ch.isdigit())
                if digits:
                    estimated_total += float(digits)
                continue
            if isinstance(asset, dict):
                item = {
                    "type": asset.get("type", "external_asset"),
                    "institution": asset.get("institution", "external provider"),
                    "value": asset.get("value", 0),
                }
                normalized.append(item)
                estimated_total += float(item.get("value", 0) or 0)
                continue
            if hasattr(asset, "get"):
                item = {
                    "type": asset.get("type", "external_asset"),
                    "institution": asset.get("institution", "external provider"),
                    "value": asset.get("value", 0),
                }
                normalized.append(item)
                estimated_total += float(item.get("value", 0) or 0)

        opportunities: list[dict[str, Any]] = []
        for asset in normalized:
            if isinstance(asset, str):
                asset_lower = asset.lower()
                if "fd" in asset_lower or "fixed" in asset_lower or "deposit" in asset_lower:
                    opportunities.append(
                        {
                            "asset_type": "fixed_deposit",
                            "institution": "external provider",
                            "value": 0,
                            "benefit": (
                                "Transfer this deposit to centralize rates, improve "
                                "visibility, and unlock integrated benefits."
                            ),
                        }
                    )
                elif "demat" in asset_lower:
                    opportunities.append(
                        {
                            "asset_type": "demat",
                            "institution": "external provider",
                            "value": 0,
                            "benefit": (
                                "Move this position to our platform for unified "
                                "reporting and better portfolio oversight."
                            ),
                        }
                    )
                continue

            if isinstance(asset, dict):
                item = {
                    "type": asset.get("type", "external_asset"),
                    "institution": asset.get("institution", "external provider"),
                    "value": asset.get("value", 0),
                }
                asset_type = str(item["type"]).lower()
                if "fixed" in asset_type or "fd" in asset_type or "deposit" in asset_type:
                    opportunities.append(
                        {
                            "asset_type": "fixed_deposit",
                            "institution": item.get("institution", "external provider"),
                            "value": item.get("value", 0),
                            "benefit": (
                                "Transfer this deposit to centralize rates, improve "
                                "visibility, and unlock integrated benefits."
                            ),
                        }
                    )
                elif "demat" in asset_type or "equity" in asset_type:
                    opportunities.append(
                        {
                            "asset_type": "demat",
                            "institution": item.get("institution", "external provider"),
                            "value": item.get("value", 0),
                            "benefit": (
                                "Move this position to our platform for unified "
                                "reporting and better portfolio oversight."
                            ),
                        }
                    )

        suggestion = (
            "Consolidating these external assets could improve visibility, reduce "
            "fragmentation, and unlock benefits without pressure."
        )
        return {
            "wallet_profile": {
                "client_id": payload.get("client_id", "unknown"),
                "external_assets": normalized,
                "consolidation_opportunities": opportunities,
                "estimated_external_assets": estimated_total,
            },
            "suggestion": suggestion,
        }

    def recommend_products(self, payload: dict[str, Any]) -> dict[str, Any]:
        client_id = str(payload.get("client_id", ""))
        kyc_status = self._verified_kyc_status(client_id)
        kyc_result = check_kyc_status(kyc_status)
        if kyc_result["requires_kyc"]:
            return {
                "status": "blocked",
                "reason": "kyc_required",
                "message": kyc_result["message"],
                "recommendations": [],
            }

        risk_appetite = payload.get("risk_appetite", "moderate")
        goal = payload.get("goal", "wealth management")
        balance = payload.get("balance", 0)
        needs = payload.get("needs", []) or []
        lower_needs = [str(item).lower() for item in needs]
        need_text = " ".join(lower_needs)

        recommendations = []
        if str(risk_appetite).lower() in {"moderate", "high", "aggressive"}:
            recommendations.append("Mutual fund SIPs aligned to your wealth-growth goal.")
        if balance >= 100000:
            recommendations.append(
                "Fixed deposit options with competitive rates for cash allocation."
            )
        if balance >= 200000:
            recommendations.append(
                "Personal loan or overdraft options for balance management and liquidity."
            )
        if payload.get("protection_need") or "protection" in need_text or "insurance" in need_text:
            recommendations.append(
                "Health insurance and direct tax payment benefits suited to your profile."
            )
            recommendations.append(
                "Fee waiver review and concierge access for priority banking benefits."
            )
        if "payment" in need_text or "payments" in need_text or "bill" in need_text:
            recommendations.append(
                "Automated bill pay and tax payment services to simplify recurring obligations."
            )
        if "fee" in need_text or "concierge" in need_text:
            recommendations.append(
                "Fee waiver review and concierge access for priority banking benefits."
            )
        recommendations.append(
            "Protected savings or premium banking benefits for balance management."
        )

        return {
            "goal": goal,
            "balance": balance,
            "recommendations": recommendations,
        }
