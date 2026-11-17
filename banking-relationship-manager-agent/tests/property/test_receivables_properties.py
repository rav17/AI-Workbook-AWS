from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from aria.agents.aria.receivables.policy import load_approved_catalogue
from aria.agents.aria.receivables.rules import calculate_variance, rank_candidates, within_tolerance

ROOT = Path(__file__).resolve().parents[2]
POLICY = load_approved_catalogue(ROOT).policy


@given(
    payment=st.integers(min_value=-10_000_000, max_value=10_000_000),
    expected=st.integers(min_value=-10_000_000, max_value=10_000_000),
)
def test_decimal_variance_is_exact_and_signed(payment: int, expected: int) -> None:
    result = calculate_variance(Decimal(payment) / 100, Decimal(expected) / 100)
    assert result == Decimal(payment - expected) / 100


@given(outstanding_cents=st.integers(min_value=1, max_value=100_000_000))
def test_tolerance_is_symmetric_and_exactly_inclusive(outstanding_cents: int) -> None:
    outstanding = Decimal(outstanding_cents) / 100
    maximum = min(POLICY.tolerance_abs, outstanding * POLICY.tolerance_pct)
    assert within_tolerance(maximum, outstanding, POLICY)
    assert within_tolerance(-maximum, outstanding, POLICY)
    assert not within_tolerance(maximum + Decimal("0.01"), outstanding, POLICY)


@given(order=st.permutations(["INV-SYN-1002", "INV-SYN-1003", "INV-SYN-1006"]))
def test_candidate_ranking_is_stable_under_equivalent_input_order(order: tuple[str, ...]) -> None:
    invoices = [
        {
            "invoice_id": invoice_id,
            "reference": invoice_id.replace("INV-SYN-", "INV"),
            "status": "open",
            "outstanding_amount": "12500.00",
        }
        for invoice_id in order
    ]
    payment = {"amount": "12500.00", "remittance_reference": "INV1002 INV1003 INV1006"}
    ranked = rank_candidates(payment, invoices, "CORP-SYN-001", "USD", POLICY)
    assert [candidate.invoice_id for candidate in ranked] == sorted(
        candidate.invoice_id for candidate in ranked
    )
