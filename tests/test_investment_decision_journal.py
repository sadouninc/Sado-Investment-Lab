from copy import deepcopy

import pytest

from scripts.investment_decision_journal import capture_decision, validate_decision, validate_review


def base_snapshot():
    return {
        "decided_at": "2026-08-09T10:30:00+09:00",
        "security_code": "6622",
        "decision": "BUY",
        "actor": "SADO",
        "confidence": "MEDIUM",
        "owner_judgment": {
            "why_now": "決算後に前提を確認できたため",
            "biggest_risk": "電力投資の鈍化",
            "what_changes_my_mind": "受注と利益率の悪化",
        },
        "system_snapshot": {
            "thesis_ref": "hypothesis:6622:dc-power",
            "valuation_ref": "valuation:6622:fy2027",
            "portfolio_ref": "portfolio:2026-08-09",
        },
        "evidence_refs": ["fact:6622:q1"],
        "retrospective_note": False,
    }


def test_deterministic_identity_and_non_mutation():
    source = base_snapshot()
    before = deepcopy(source)
    a = validate_decision(source)
    b = validate_decision(source)
    assert a["decision_id"] == b["decision_id"]
    assert source == before


def test_owner_judgment_required_and_separate_from_system_snapshot():
    source = base_snapshot()
    del source["owner_judgment"]["why_now"]
    with pytest.raises(ValueError):
        validate_decision(source)


def test_identical_retry_is_idempotent_but_rewrite_rejected():
    source = base_snapshot()
    saved = capture_decision(source)
    assert capture_decision(source, saved) == saved
    changed = base_snapshot()
    changed["owner_judgment"]["why_now"] = "後から書き換え"
    with pytest.raises(ValueError, match="immutable"):
        capture_decision(changed, saved)


def test_retrospective_note_is_explicit():
    source = base_snapshot()
    source["retrospective_note"] = True
    assert validate_decision(source)["retrospective_note"] is True


def test_naive_timestamp_rejected():
    source = base_snapshot()
    source["decided_at"] = "2026-08-09T10:30:00"
    with pytest.raises(ValueError, match="timezone"):
        validate_decision(source)


def test_review_keeps_decision_quality_and_outcome_independent():
    decision = validate_decision(base_snapshot())
    review = validate_review(
        {
            "decision_id": decision["decision_id"],
            "reviewed_at": "2026-11-05T15:30:00+09:00",
            "trigger": "EARNINGS",
            "what_happened": "前提は維持したが株価は下落",
            "decision_quality": "GOOD",
            "outcome": "NEGATIVE",
            "mistake_tags": [],
        },
        decision_id=decision["decision_id"],
    )
    assert review["decision_quality"] == "GOOD"
    assert review["outcome"] == "NEGATIVE"


def test_review_wrong_decision_ref_rejected():
    with pytest.raises(ValueError, match="mismatch"):
        validate_review(
            {
                "decision_id": "decision:other",
                "reviewed_at": "2026-11-05T15:30:00+09:00",
                "trigger": "EARNINGS",
                "what_happened": "x",
                "decision_quality": "MIXED",
                "outcome": "FLAT",
            },
            decision_id="decision:expected",
        )
