from scripts.decision_execution_fidelity import compare_execution


def test_unknown_actual_action_stays_not_judgable_without_owner_intent_inference():
    intent = {
        "decision_ref": "decision:6622:unknown-action",
        "security_code": "6622",
        "action": "BUY",
        "intended_quantity": None,
        "intended_notional": None,
        "price_condition": {"type": "UNKNOWN"},
        "timing_condition": {"session": "UNKNOWN"},
        "account_type": "UNKNOWN",
        "captured_at": "2026-08-09T10:30:00+09:00",
        "source": "OWNER_EXPLICIT",
    }
    actual = {
        "decision_ref": "decision:6622:unknown-action",
        "security_code": "6622",
        "captured_at": "2026-08-09T13:30:00+09:00",
        "actual_action": "UNKNOWN",
        "execution_status": "EXECUTED",
        "source_status": "CURRENT",
        "fills": [
            {
                "executed_at": "2026-08-09T13:12:00+09:00",
                "side": "BUY",
                "quantity": 100,
                "price": 12340,
                "account_type": "CASH",
                "source_ref": "sbi:fill:unknown-action",
                "session": "PM",
            }
        ],
    }

    result = compare_execution(intent, actual)

    assert result["overall"] == "MATCH"
    assert result["dimensions"]["action"] == "NOT_JUDGABLE"
    assert "ACTION_MISMATCH" not in result["deviations"]
