from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from research_debt import validate_debt
from research_debt_evidence import (
    ResearchDebtEvidenceError,
    expected_evidence_key,
    resolve_evidence_availability,
)


def debt_fixture(*, status="WAITING_FOR_EVIDENCE", materiality="HIGH"):
    return validate_debt(
        {
            "security_code": "6622",
            "section": "base_scenario",
            "question": "Energy Management受注残は想定期間内に売上化しているか",
            "origin_type": "OWNER_ASSUMPTION",
            "origin_ref": "scenario:6622:base",
            "created_at": "2026-08-09T14:00:00+09:00",
            "materiality": materiality,
            "expected_evidence": [
                {
                    "type": "EARNINGS",
                    "description": "Q2 segment order/revenue/margin",
                    "not_before": "2026-11-01",
                    "expected_by": "2026-11-10",
                }
            ],
            "status": status,
        }
    )


def matching_artifact(*, published_at="2026-11-05T15:30:00+09:00", source_ref="earnings:6622:2026-q2"):
    expected = debt_fixture()["expected_evidence"][0]
    return {
        "type": "EARNINGS",
        "source_ref": source_ref,
        "evidence_key": expected_evidence_key(expected),
        "published_at": published_at,
    }


def test_waiting_evidence_stays_waiting_before_artifact_exists():
    source = debt_fixture()
    result = resolve_evidence_availability(source, [], as_of="2026-10-15T09:00:00+09:00")
    assert result["suggested_status"] == "WAITING_FOR_EVIDENCE"
    assert result["availability_status"] == "NOT_AVAILABLE"
    assert result["expected_by_passed_without_evidence"] is False
    assert result["hypothesis_mutation"] is None
    assert result["trade_recommendation"] is None


def test_new_explicitly_related_artifact_makes_evidence_available():
    source = debt_fixture()
    artifact = matching_artifact()
    result = resolve_evidence_availability(
        source,
        [artifact],
        as_of="2026-11-05T16:00:00+09:00",
    )
    assert result["suggested_status"] == "EVIDENCE_AVAILABLE"
    assert result["availability_status"] == "AVAILABLE"
    assert result["matching_evidence"] == [
        {
            "type": "EARNINGS",
            "source_ref": "earnings:6622:2026-q2",
            "evidence_key": artifact["evidence_key"],
            "timestamp_field": "published_at",
            "artifact_time": "2026-11-05T15:30:00+09:00",
        }
    ]


def test_same_type_without_explicit_evidence_key_does_not_match():
    source = debt_fixture()
    unrelated = matching_artifact()
    unrelated["evidence_key"] = "evidence:earnings:unrelated"
    result = resolve_evidence_availability(
        source,
        [unrelated],
        as_of="2026-11-05T16:00:00+09:00",
    )
    assert result["suggested_status"] == "WAITING_FOR_EVIDENCE"
    assert result["matching_evidence"] == []


def test_artifact_must_be_after_debt_creation_and_not_before_boundary():
    source = debt_fixture()
    too_early = matching_artifact(published_at="2026-08-08T15:30:00+09:00")
    before_window = matching_artifact(published_at="2026-10-31T15:30:00+09:00")
    result = resolve_evidence_availability(
        source,
        [too_early, before_window],
        as_of="2026-11-05T16:00:00+09:00",
    )
    assert result["suggested_status"] == "WAITING_FOR_EVIDENCE"
    assert result["matching_evidence"] == []


def test_date_only_same_day_cannot_prove_artifact_after_datetime_creation():
    source = debt_fixture()
    expected = source["expected_evidence"][0]
    artifact = {
        "type": "EARNINGS",
        "source_ref": "earnings:6622:same-day",
        "evidence_key": expected_evidence_key(expected),
        "as_of": "2026-08-09",
    }
    # The same-day date-only artifact has insufficient precision to prove that
    # it appeared after the 14:00 debt creation time.
    source["expected_evidence"][0]["not_before"] = "2026-08-09"
    result = resolve_evidence_availability(
        source,
        [artifact],
        as_of="2026-08-10T09:00:00+09:00",
    )
    assert result["matching_evidence"] == []


def test_overdue_without_evidence_is_diagnostic_only_not_hypothesis_invalidation():
    source = debt_fixture()
    result = resolve_evidence_availability(
        source,
        [],
        as_of="2026-11-20T09:00:00+09:00",
    )
    assert result["expected_by_passed_without_evidence"] is True
    assert result["suggested_status"] == "WAITING_FOR_EVIDENCE"
    assert result["hypothesis_mutation"] is None
    assert "BROKEN" not in str(result)


def test_incomplete_artifact_scope_does_not_treat_missing_as_absence():
    source = debt_fixture()
    result = resolve_evidence_availability(
        source,
        [],
        as_of="2026-11-20T09:00:00+09:00",
        artifact_scope="INCOMPLETE",
    )
    assert result["availability_status"] == "UNKNOWN"
    assert result["suggested_status"] == source["status"]


def test_review_due_requires_explicit_signal_and_materiality():
    source = debt_fixture(materiality="HIGH")
    result = resolve_evidence_availability(
        source,
        [matching_artifact()],
        as_of="2026-11-05T16:00:00+09:00",
        review_due=True,
    )
    assert result["suggested_status"] == "REVIEW_DUE"

    low = debt_fixture(materiality="LOW")
    with pytest.raises(ResearchDebtEvidenceError):
        resolve_evidence_availability(
            low,
            [matching_artifact()],
            as_of="2026-11-05T16:00:00+09:00",
            review_due=True,
        )


def test_existing_review_due_is_not_silently_demoted():
    source = debt_fixture(status="REVIEW_DUE")
    result = resolve_evidence_availability(
        source,
        [],
        as_of="2026-11-20T09:00:00+09:00",
        artifact_scope="INCOMPLETE",
    )
    assert result["suggested_status"] == "REVIEW_DUE"


def test_timezone_naive_artifact_datetime_fails_closed():
    source = debt_fixture()
    artifact = matching_artifact(published_at="2026-11-05T15:30:00")
    with pytest.raises(ResearchDebtEvidenceError):
        resolve_evidence_availability(
            source,
            [artifact],
            as_of="2026-11-05T16:00:00+09:00",
        )


def test_artifact_timestamp_is_unambiguous_exactly_one_field():
    source = debt_fixture()
    artifact = matching_artifact()
    artifact["observed_at"] = "2026-11-05T15:31:00+09:00"
    with pytest.raises(ResearchDebtEvidenceError):
        resolve_evidence_availability(
            source,
            [artifact],
            as_of="2026-11-05T16:00:00+09:00",
        )


def test_deterministic_and_non_mutating():
    source = debt_fixture()
    artifacts = [matching_artifact()]
    source_before = deepcopy(source)
    artifacts_before = deepcopy(artifacts)
    first = resolve_evidence_availability(
        source,
        artifacts,
        as_of="2026-11-05T16:00:00+09:00",
    )
    second = resolve_evidence_availability(
        source,
        artifacts,
        as_of="2026-11-05T16:00:00+09:00",
    )
    assert first == second
    assert source == source_before
    assert artifacts == artifacts_before


def test_no_trade_recommendation_is_generated():
    result = resolve_evidence_availability(
        debt_fixture(),
        [matching_artifact()],
        as_of="2026-11-05T16:00:00+09:00",
    )
    assert result["trade_recommendation"] is None
    payload = str(result)
    assert "BUY" not in payload
    assert "SELL" not in payload
    assert "DO_NOT_TRADE" not in payload
