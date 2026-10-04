from __future__ import annotations

from src.sado_investment_lab.domain.boj_early_warning import classify_boj_signal


def test_legacy_shape_is_classified_by_canonical_classifier() -> None:
    result = classify_boj_signal(
        {
            "boj_state": "RED",
            "market_implied_probability": 0.8,
            "market_probability_only": True,
        }
    ).to_dict()

    assert result["effective_state"] == "ORANGE"
    assert result["probability_only"] is True


def test_valid_primary_evidence_can_classify_red() -> None:
    result = classify_boj_signal(
        {
            "primary_evidence_present": True,
            "evidence_status": "VALID",
            "indicates_near_term_tightening": True,
            "evidence_refs": [
                {
                    "ref_id": "boj-primary-1",
                    "source_title": "BOJ primary evidence",
                    "evidence_type": "STATEMENT",
                }
            ],
        }
    ).to_dict()

    assert result["effective_state"] == "RED"
    assert result["primary_evidence_present"] is True
    assert result["evidence_refs"][0]["ref_id"] == "boj-primary-1"
