"""Disclosure manager for financial safety and compliance. Traces: R15, R31, R33, R35, R36."""
from config.models import ExecutionResult, Confidence
from config.settings import ScopeLimitationConfig

FINANCIAL_DISCLAIMER = (
    "This advice is informational only and not a substitute for professional financial counsel. "
    "Past performance does not guarantee future results."
)

NON_FIDUCIARY_DISCLAIMER = (
    "This system does not act as a fiduciary advisor. Recommended products may carry "
    "associated commissions or incentives. Please independently verify all recommendations."
)

LOAN_DISCLAIMER = (
    "Facilitation improves chances but does not guarantee approval. Final approval depends on "
    "credit score, income verification, and risk assessment by the lending institution."
)

PRODUCT_CATALOG_DISCLOSURE = (
    "Recommendations are sourced from the bank's Product Catalog and do not represent the full market. "
    "This system is not an independent financial advisor."
)

COMMISSION_DISCLOSURE = (
    "Recommended products may carry associated commissions or incentives for the banking institution. "
    "Please consider this when evaluating recommendations."
)

LOW_CONFIDENCE_WARNING = "This recommendation has reduced confidence. Please exercise additional caution."

ADVISORY_DOMAINS = {"investment_advice", "savings_advice", "loan_advice"}

# Domains that trigger non-fiduciary disclaimer (R33)
NON_FIDUCIARY_DOMAINS = {"investment_advice", "savings_advice"}

# Domains that trigger product catalog disclosure (R31)
PRODUCT_CATALOG_DOMAINS = {"investment_advice", "savings_advice", "loan_advice"}

# Domains that trigger commission disclosure (R33.2)
COMMISSION_DOMAINS = {"investment_advice", "savings_advice", "loan_advice"}


class DisclosureManager:
    """Attaches mandatory disclosures to ExecutionResults. Traces: R15, R31, R33, R35, R36."""

    def __init__(self, scope_config: ScopeLimitationConfig | None = None):
        self.scope_config = scope_config or ScopeLimitationConfig()

    def apply_disclosures(self, result: ExecutionResult, worker_domain: str | None = None) -> ExecutionResult:
        """Apply all applicable disclosures based on worker domain.

        Traces: R15.1, R15.2, R31, R33, R35, R36.
        """
        domain = worker_domain or result.worker_domain

        # Base financial disclaimer for advisory domains (R15)
        if domain in ADVISORY_DOMAINS:
            result.disclaimer = FINANCIAL_DISCLAIMER

        # Non-fiduciary disclaimer for investment/product advice (R33)
        if domain in NON_FIDUCIARY_DOMAINS:
            result = self.attach_non_fiduciary(result)

        # Product catalog disclosure (R31)
        if domain in PRODUCT_CATALOG_DOMAINS:
            result = self.attach_product_catalog_disclosure(result)

        # Loan disclaimer (R35)
        if domain == "loan_advice":
            result = self.attach_loan_disclaimer(result)

        # Commission disclosure (R33.2)
        if domain in COMMISSION_DOMAINS:
            result = self.attach_commission_disclosure(result)

        # Low confidence warning (R15.3)
        if result.confidence == Confidence.LOW:
            result.issues.append(LOW_CONFIDENCE_WARNING)
            result.low_confidence_warning = LOW_CONFIDENCE_WARNING

        return result

    def attach_non_fiduciary(self, result: ExecutionResult) -> ExecutionResult:
        """Attach non-fiduciary disclaimer for investment/product advice. Traces: R33.1, R33.3."""
        result.non_fiduciary_disclaimer = NON_FIDUCIARY_DISCLAIMER
        if result.disclaimer:
            result.disclaimer += " " + NON_FIDUCIARY_DISCLAIMER
        else:
            result.disclaimer = NON_FIDUCIARY_DISCLAIMER
        return result

    def attach_product_catalog_disclosure(self, result: ExecutionResult) -> ExecutionResult:
        """Set recommendation_source and add catalog disclosure. Traces: R31.1, R31.3."""
        result.recommendation_source = "product_catalog"
        if result.disclaimer:
            result.disclaimer += " " + PRODUCT_CATALOG_DISCLOSURE
        else:
            result.disclaimer = PRODUCT_CATALOG_DISCLOSURE
        return result

    def attach_loan_disclaimer(self, result: ExecutionResult) -> ExecutionResult:
        """Attach loan approval limitation disclaimer. Traces: R35.2."""
        if result.disclaimer:
            result.disclaimer += " " + LOAN_DISCLAIMER
        else:
            result.disclaimer = LOAN_DISCLAIMER
        if LOAN_DISCLAIMER not in result.issues:
            result.issues.append(LOAN_DISCLAIMER)
        return result

    def attach_scope_limitation(self, result: ExecutionResult, request_context: str) -> ExecutionResult:
        """Check if request touches out-of-scope services and add scope_limitation. Traces: R36.2, R36.3."""
        out_of_scope = self.scope_config.out_of_scope_services
        matched = [
            svc for svc in out_of_scope
            if svc.replace("_", " ") in request_context.lower()
            or svc in request_context.lower()
        ]
        if matched:
            limitation_msg = (
                f"The following services are outside the scope of this system: "
                f"{', '.join(s.replace('_', ' ') for s in matched)}. "
                "Please consult a qualified professional for these services."
            )
            result.scope_limitation = limitation_msg
            result.issues.append(limitation_msg)
        return result

    def attach_commission_disclosure(self, result: ExecutionResult) -> ExecutionResult:
        """Add commission/incentive transparency note. Traces: R33.2."""
        result.commission_disclosure = COMMISSION_DISCLOSURE
        return result
