"""Tests for financial tools. Traces: R3, R4, R5, R6, R8."""
import json
import pytest
from hypothesis import given, settings, strategies as st

from tools.financial_tools import (
    transaction_fetcher,
    balance_checker,
    investment_data_api,
    budgeting_calculator,
)


# --- Strategies ---

user_id_st = st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N")))
days_st = st.integers(min_value=1, max_value=365)
income_st = st.floats(min_value=100.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
savings_pct_st = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
risk_st = st.sampled_from(["low", "medium", "high"])
query_st = st.text(min_size=1, max_size=100)


# --- transaction_fetcher tests (R3) ---

class TestTransactionFetcher:
    """Validates: Requirements R3"""

    def test_returns_valid_json_with_transactions(self):
        result = json.loads(transaction_fetcher(user_id="user1", days=30))
        assert result["user_id"] == "user1"
        assert result["days"] == 30
        assert isinstance(result["transactions"], list)
        assert len(result["transactions"]) > 0
        assert "total_spent" in result

    def test_default_days(self):
        result = json.loads(transaction_fetcher(user_id="user1"))
        assert result["days"] == 30

    def test_transaction_structure(self):
        result = json.loads(transaction_fetcher(user_id="u1", days=7))
        for txn in result["transactions"]:
            assert "date" in txn
            assert "category" in txn
            assert "amount" in txn
            assert "merchant" in txn
            assert isinstance(txn["amount"], (int, float))

    def test_total_spent_matches_sum(self):
        result = json.loads(transaction_fetcher(user_id="u1"))
        expected = sum(t["amount"] for t in result["transactions"])
        assert abs(result["total_spent"] - expected) < 0.01

    @given(uid=user_id_st, d=days_st)
    @settings(max_examples=50)
    def test_always_returns_parseable_json(self, uid, d):
        """Property: transaction_fetcher always returns valid JSON with required keys."""
        result = json.loads(transaction_fetcher(user_id=uid, days=d))
        assert "user_id" in result
        assert "days" in result
        assert "transactions" in result
        assert "total_spent" in result
        assert result["user_id"] == uid
        assert result["days"] == d


# --- balance_checker tests (R4) ---

class TestBalanceChecker:
    """Validates: Requirements R4"""

    def test_returns_valid_json_with_balances(self):
        result = json.loads(balance_checker(user_id="user1"))
        assert result["user_id"] == "user1"
        assert "checking" in result
        assert "savings" in result
        assert "investment" in result
        assert "total" in result

    def test_total_is_sum_of_accounts(self):
        result = json.loads(balance_checker(user_id="u1"))
        expected = result["checking"] + result["savings"] + result["investment"]
        assert abs(result["total"] - expected) < 0.01

    @given(uid=user_id_st)
    @settings(max_examples=50)
    def test_always_returns_parseable_json(self, uid):
        """Property: balance_checker always returns valid JSON with required keys."""
        result = json.loads(balance_checker(user_id=uid))
        assert "user_id" in result
        assert "checking" in result
        assert "savings" in result
        assert result["user_id"] == uid


# --- investment_data_api tests (R5) ---

class TestInvestmentDataApi:
    """Validates: Requirements R5"""

    def test_returns_valid_json_with_options(self):
        result = json.loads(investment_data_api(query="stocks", risk_tolerance="medium"))
        assert result["query"] == "stocks"
        assert result["risk_tolerance"] == "medium"
        assert isinstance(result["options"], list)
        assert len(result["options"]) > 0

    def test_default_risk_tolerance(self):
        result = json.loads(investment_data_api(query="bonds"))
        assert result["risk_tolerance"] == "medium"

    @pytest.mark.parametrize("risk", ["low", "medium", "high"])
    def test_options_match_risk_level(self, risk):
        result = json.loads(investment_data_api(query="test", risk_tolerance=risk))
        for opt in result["options"]:
            assert opt["risk"] == risk

    def test_option_structure(self):
        result = json.loads(investment_data_api(query="test"))
        for opt in result["options"]:
            assert "name" in opt
            assert "expected_return" in opt
            assert "risk" in opt
            assert "type" in opt

    @given(q=query_st, r=risk_st)
    @settings(max_examples=50)
    def test_always_returns_parseable_json(self, q, r):
        """Property: investment_data_api always returns valid JSON with required keys."""
        result = json.loads(investment_data_api(query=q, risk_tolerance=r))
        assert "query" in result
        assert "risk_tolerance" in result
        assert "options" in result
        assert result["query"] == q
        assert result["risk_tolerance"] == r


# --- budgeting_calculator tests (R6) ---

class TestBudgetingCalculator:
    """Validates: Requirements R6"""

    def test_returns_valid_json_with_breakdown(self):
        result = json.loads(budgeting_calculator(user_id="u1", income=5000.0))
        assert result["user_id"] == "u1"
        assert result["monthly_income"] == 5000.0
        assert "target_savings" in result
        assert "recommended_allocation" in result
        assert "annual_savings_potential" in result

    def test_default_savings_pct(self):
        result = json.loads(budgeting_calculator(user_id="u1", income=5000.0))
        assert result["target_savings"] == 1000.0  # 20% of 5000

    def test_custom_savings_pct(self):
        result = json.loads(budgeting_calculator(user_id="u1", income=10000.0, target_savings_pct=30.0))
        assert result["target_savings"] == 3000.0

    def test_allocation_sums_to_income(self):
        result = json.loads(budgeting_calculator(user_id="u1", income=6000.0, target_savings_pct=20.0))
        alloc = result["recommended_allocation"]
        total = alloc["needs"] + alloc["wants"] + alloc["savings"]
        assert abs(total - 6000.0) < 0.01

    def test_annual_savings_potential(self):
        result = json.loads(budgeting_calculator(user_id="u1", income=5000.0, target_savings_pct=10.0))
        assert result["annual_savings_potential"] == result["target_savings"] * 12

    @given(uid=user_id_st, inc=income_st, pct=savings_pct_st)
    @settings(max_examples=50)
    def test_always_returns_parseable_json(self, uid, inc, pct):
        """Property: budgeting_calculator always returns valid JSON with required keys."""
        result = json.loads(budgeting_calculator(user_id=uid, income=inc, target_savings_pct=pct))
        assert "user_id" in result
        assert "monthly_income" in result
        assert "target_savings" in result
        assert "recommended_allocation" in result
        assert result["user_id"] == uid
        assert abs(result["monthly_income"] - inc) < 0.01
