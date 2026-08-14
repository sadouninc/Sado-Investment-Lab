from scripts.operational_state_guard import (
    split_away_blockers,
    validate_mode_transition,
)


def test_mode_transition_compare_and_set_allows_fresh_transition():
    result = validate_mode_transition(
        current_mode="ACTIVE",
        expected_current_mode="ACTIVE",
        target_mode="AWAY",
        transition_id="2026-08-15T0212+0900-away",
        last_transition_id="previous-active",
    )
    assert result.allowed is True
    assert result.status == "TRANSITION_ALLOWED"


def test_stale_transition_fails_closed():
    result = validate_mode_transition(
        current_mode="ACTIVE",
        expected_current_mode="AWAY",
        target_mode="ACTIVE",
        transition_id="stale-active-pr",
    )
    assert result.allowed is False
    assert result.status == "STALE_EXPECTED_MODE"


def test_duplicate_transition_id_fails_closed():
    result = validate_mode_transition(
        current_mode="AWAY",
        expected_current_mode="AWAY",
        target_mode="ACTIVE",
        transition_id="same",
        last_transition_id="same",
    )
    assert result.allowed is False
    assert result.status == "DUPLICATE_TRANSITION_ID"


def test_owner_authority_is_separated_from_autonomous_blockers():
    split = split_away_blockers(
        [
            {"class": "OWNER_AUTHORITY", "detail": "threshold decision", "ref": "#550"},
            {"class": "REVIEW_WAIT", "detail": "design re-gate", "ref": "#584"},
            {"class": "CI_FAILURE", "detail": "tests failed", "ref": "#999"},
        ]
    )
    assert [item["ref"] for item in split["owner_authority"]] == ["#550"]
    assert [item["ref"] for item in split["autonomous"]] == ["#584", "#999"]
