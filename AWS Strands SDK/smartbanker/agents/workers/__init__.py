"""Worker agent factory functions and classes."""
from agents.workers.spending_analyzer import create_spending_analyzer
from agents.workers.savings_advisor import create_savings_advisor
from agents.workers.investment_advisor import create_investment_advisor
from agents.workers.query_assistant import create_query_assistant
from agents.workers.risk_compliance import create_risk_compliance, RiskComplianceAgent
from agents.workers.service_request_handler import create_service_request_handler, ServiceRequestHandlerAgent
from agents.workers.loan_advisor import create_loan_advisor, LoanAdvisorAgent
from agents.workers.value_assessor import create_value_assessor, ValueAssessorAgent

__all__ = [
    "create_spending_analyzer",
    "create_savings_advisor",
    "create_investment_advisor",
    "create_query_assistant",
    "create_risk_compliance",
    "RiskComplianceAgent",
    "create_service_request_handler",
    "ServiceRequestHandlerAgent",
    "create_loan_advisor",
    "LoanAdvisorAgent",
    "create_value_assessor",
    "ValueAssessorAgent",
]
