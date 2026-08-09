from copy import deepcopy

import pytest

from scripts.decision_execution_fidelity import (
    capture_actual_execution,
    capture_execution_intent,
    classify_unjournaled_execution,
    compare_execution,
    validate_actual_execution,
    validate_execution_intent,
)


def base_intent():
    return {
        "decision_ref": "decision:6622:buy-001",
        "security_code": "6622",
        "action": "BUY",
        "intended_quantity": 100,
        "intended_notional": None,
        "price_condition": {"type": "LIMIT", "value": 12500},
        "timing_condition": {
            "execute_by": "2026-08-09T14:00:00+09:00",
            "session": "PM",
        },
        "account_type": "CASH",
        "captured_at": "2026-08-09T10:30:00+09:00",
        "source": "OWNER_EXPLICIT",
    }


def base_actual():
    return {
        "decision_ref": "decision:6622:buy-001",
        "security_code": "6622",
        "captured_at": "2026-08-09T13:30:00+09:00",
        "actual_action": "BUY",
        "fills": [
            {
                "executed_at": "2026-08-09T13:12:00+09:00",
                "side": "BUY",
                "quantity": 100,
                "price": 12340,
                "account_type": "CASH",
                "source_ref": "sbi:fill:001",
                "session": "PM",
            }
        ],
        "execution_status": "EXECUTED",
        "source_status": "CURRENT",
        "position_before_ref": "portfolio:before",
        "position_after_ref": "portfolio:after",
    }


def test_buy_100_actual_buy_100_matches_only_judgable_fields():
    result = compare_execution(base_intent(), base_actual())
    assert result["overall"] == "MATCH"
    assert result["dimensions"] == {
        "action": "MATCH",
        "quantity": "MATCH",
        "price": "MATCH",
        "timing": "MATCH",
        "account": "MATCH",
        "completion": "MATCH",
    }
    assert result["deviations"] == []


def test_reduce_intent_actual_new_short_is_action_mismatch():
    intent = base_intent()
    intent.update(
        {
            "action": "REDUCE",
            "price_condition": {"type": "UNKNOWN"},
            "timing_condition": {"session": "UNKNOWN"},
            "account_type": "MARGIN",
        }
    )
    actual = base_actual()
    actual["actual_action"] = "SHORT_OPEN"
    actual["fills"][0].update({"side": "SELL", "account_type": "MARGIN"})
    result = compare_execution(intent, actual)
    assert result["overall"] == "MISMATCH"
    assert result["dimensions"]["action"] == "MISMATCH"
    assert "ACTION_MISMATCH" in result["deviations"]


def test_quantity_100_actual_200_is_mismatch():
    actual = base_actual()
    actual["fills"][0]["quantity"] = 200
    result = compare_execution(base_intent(), actual)
    assert result["overall"] == "MISMATCH"
    assert result["dimensions"]["quantity"] == "MISMATCH"
    assert "QUANTITY_MISMATCH" in result["deviations"]


def test_missing_intended_quantity_is_not_judgable_not_inferred():
    intent = base_intent()
    intent["intended_quantity"] = None
    result = compare_execution(intent, base_actual())
    assert result["dimensions"]["quantity"] == "NOT_JUDGABLE"
    assert result["overall"] == "MATCH"


def test_missing_price_condition_is_not_judgable():
    intent = base_intent()
    intent["price_condition"] = {"type": "UNKNOWN"}
    result = compare_execution(intent, base_actual())
    assert result["dimensions"]["price"] == "NOT_JUDGABLE"
    assert "PRICE_CONDITION_MISMATCH" not in result["deviations"]


def test_limit_price_violation_is_structural_mismatch():
    actual = base_actual()
    actual["fills"][0]["price"] = 12600
    result = compare_execution(base_intent(), actual)
    assert result["dimensions"]["price"] == "MISMATCH"
    assert "PRICE_CONDITION_MISMATCH" in result["deviations"]


def test_no_fill_is_not_executed():
    actual = base_actual()
    actual.update({"fills": [], "actual_action": "UNKNOWN", "execution_status": "NOT_EXECUTED"})
    result = compare_execution(base_intent(), actual)
    assert result["overall"] == "NOT_EXECUTED"
    assert result["dimensions"]["completion"] == "NOT_EXECUTED"
    assert result["deviations"] == ["NOT_EXECUTED"]


def test_partial_fill_is_partial_match_when_other_judgable_fields_match():
    intent = base_intent()
    intent["intended_quantity"] = None
    actual = base_actual()
    actual["fills"][0]["quantity"] = 40
    actual["execution_status"] = "PARTIAL"
    result = compare_execution(intent, actual)
    assert result["overall"] == "PARTIAL_MATCH"
    assert result["dimensions"]["completion"] == "PARTIAL_MATCH"
    assert "PARTIAL_FILL" in result["deviations"]


def test_source_missing_is_unknown_not_negative_or_zero():
    actual = base_actual()
    actual.update(
        {
            "fills": [],
            "actual_action": "UNKNOWN",
            "execution_status": "UNKNOWN",
            "source_status": "UNAVAILABLE",
        }
    )
    result = compare_execution(base_intent(), actual)
    assert result["overall"] == "UNKNOWN"
    assert set(result["dimensions"].values()) == {"UNKNOWN"}
    assert result["deviations"] == ["UNKNOWN"]


def test_same_input_is_deterministic_idempotent_and_non_mutating():
    intent = base_intent()
    actual = base_actual()
    before_intent = deepcopy(intent)
    before_actual = deepcopy(actual)
    saved_intent = capture_execution_intent(intent)
    saved_actual = capture_actual_execution(actual)
    assert capture_execution_intent(intent, saved_intent) == saved_intent
    assert capture_actual_execution(actual, saved_actual) == saved_actual
    assert validate_execution_intent(intent)["execution_intent_id"] == saved_intent["execution_intent_id"]
    assert validate_actual_execution(actual)["execution_snapshot_id"] == saved_actual["execution_snapshot_id"]
    assert intent == before_intent
    assert actual == before_actual


def test_conflicting_same_identity_is_rejected():
    saved = capture_execution_intent(base_intent())
    changed = base_intent()
    changed["intended_quantity"] = 200
    with pytest.raises(ValueError, match="immutable"):
        capture_execution_intent(changed, saved)


def test_actual_fill_cannot_be_used_to_infer_owner_intent():
    with pytest.raises(ValueError, match="do not infer Owner intent"):
        compare_execution(None, base_actual())


def test_unjournaled_execution_marks_gap_without_inventing_intent():
    result = classify_unjournaled_execution(base_actual())
    assert result["deviation"] == "UNJOURNALED_EXECUTION"
    assert result["intent_inferred"] is False


def test_invalid_numeric_and_future_fill_fail_closed():
    intent = base_intent()
    intent["intended_quantity"] = True
    with pytest.raises(ValueError, match="positive integer"):
        validate_execution_intent(intent)

    actual = base_actual()
    actual["fills"][0]["executed_at"] = "2026-08-09T14:00:00+09:00"
    with pytest.raises(ValueError, match="after snapshot"):
        validate_actual_execution(actual)
