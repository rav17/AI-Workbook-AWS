from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from aria.agents.aria.statement_explainer.models import StatementTransaction
from aria.agents.aria.statement_explainer.tools import categorise_spend, get_transactions


def _generated_rows(entries: list[tuple[Decimal, str]]) -> list[StatementTransaction]:
    balance = Decimal("50000.00")
    rows = []
    for index, (amount, direction) in enumerate(entries):
        balance += amount if direction == "C" else -amount
        rows.append(
            StatementTransaction(
                trans_id=f"PROPERTY-{index}",
                value_date=f"2026-03-{index % 28 + 1:02d}",
                amount=amount,
                dr_cr_ind=direction,
                narrative=f"Generated row {index}",
                category="utilities" if direction == "D" else "salary",
                balance_after=balance,
                currency="INR",
            )
        )
    return rows


@given(
    st.lists(
        st.tuples(
            st.decimals(min_value=0, max_value=10000, places=2, allow_nan=False, allow_infinity=False),
            st.sampled_from(["D", "C"]),
        ),
        min_size=1,
        max_size=30,
    )
)
def test_debit_credit_rows_reconcile_running_balance(
    entries: list[tuple[Decimal, str]],
) -> None:
    rows = _generated_rows(entries)
    balance = Decimal("50000.00")

    for row in rows:
        balance += row.amount if row.dr_cr_ind == "C" else -row.amount
        assert row.balance_after == balance


@given(
    st.lists(
        st.decimals(min_value=0, max_value=100000, places=2, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=100,
    )
)
def test_decimal_aggregates_are_order_independent(amounts: list[Decimal]) -> None:
    assert sum(amounts, Decimal("0")) == sum(reversed(amounts), Decimal("0"))


@given(
    st.lists(
        st.tuples(
            st.decimals(min_value=0, max_value=10000, places=2, allow_nan=False, allow_infinity=False),
            st.sampled_from(["D", "C"]),
        ),
        min_size=1,
        max_size=30,
    ),
    st.decimals(min_value=0, max_value=10000, places=2, allow_nan=False, allow_infinity=False),
)
def test_minimum_amount_filter_never_returns_below_threshold(
    entries: list[tuple[Decimal, str]],
    threshold: Decimal,
) -> None:
    rows = _generated_rows(entries)
    matches = get_transactions(rows, min_amount=threshold)

    assert all(Decimal(row["amount"]) >= threshold for row in matches)
    assert len(matches) <= 100


def test_category_totals_equal_authorized_input_debits() -> None:
    rows = _generated_rows(
        [
            (Decimal("10.00"), "D"),
            (Decimal("20.00"), "D"),
            (Decimal("30.00"), "C"),
        ]
    )

    result = categorise_spend(rows, "2026-03-01", "2026-03-31")

    assert result["category_totals"] == {"utilities": Decimal("30.00")}
    assert set(result["transaction_ids"]) == {"PROPERTY-0", "PROPERTY-1"}
