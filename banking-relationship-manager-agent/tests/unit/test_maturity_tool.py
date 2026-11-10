from aria.tools.maturity_tool import evaluate_maturity_event, evaluate_outflow_event


def test_maturity_at_exactly_30_days_notifies_with_reinvestment_options():
    result = evaluate_maturity_event({"days_to_maturity": 30, "amount": 150000})

    assert result["status"] == "notify"
    assert result["recommended_action"] == "review_reinvestment"
    assert result["reinvestment_options"]
    assert result["rate_reference"] == "Current bank fixed-deposit rates"


def test_maturity_at_31_days_is_monitored():
    result = evaluate_maturity_event({"days_to_maturity": 31, "amount": 150000})

    assert result["status"] == "monitor"
    assert result["recommended_action"] == "continue_tracking"


def test_outflow_threshold_is_inclusive():
    result = evaluate_outflow_event({"amount": 100000, "threshold_amount": 100000})

    assert result["status"] == "alert"
    assert result["recommended_action"] == "rebalance_portfolio"


def test_outflow_below_threshold_continues_tracking():
    result = evaluate_outflow_event({"amount": 99999, "threshold_amount": 100000})

    assert result["status"] == "monitor"
    assert result["recommended_action"] == "continue_tracking"
