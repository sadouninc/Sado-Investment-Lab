import pytest

from scripts.intraday_subsector_validation_corpus import (
    append_annotation,
    append_observation,
    observation_identity,
    replay_observations,
)


def snapshot(observed_at="2026-08-14T09:30:00+09:00"):
    return {
        "schema_version": 1,
        "observed_at": observed_at,
        "source": "fixture:constituent-observations",
        "freshness": "FRESH",
        "data_completeness": "COMPLETE",
        "benchmark": "TOPIX",
        "sector": {"id": "pharmaceutical", "label": "Pharmaceutical", "medium_term_regime": "COLD"},
        "subsector": {
            "id": "biotechnology",
            "label": "Biotechnology",
            "taxonomy_version": "fixture-v1",
            "as_of": "2026-08-14",
            "source_or_authority": "fixture:explicit-membership",
        },
        "observations": {
            "intraday_return": 0.036,
            "benchmark_return": 0.009,
            "relative_return": 0.027,
            "rising_count": 7,
            "constituent_count": 9,
            "breadth": 7 / 9,
            "median_constituent_return": 0.031,
            "turnover_ratio": 1.8,
            "concentration_top1": 0.31,
        },
        "leaders": [{"security_code": "4588", "name": "Oncolys Bio", "intraday_return": 0.077}],
        "flow_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
    }


def test_append_is_idempotent_and_unlabeled_is_valid():
    corpus = append_observation({}, snapshot())
    corpus = append_observation(corpus, snapshot())
    assert len(corpus["observations"]) == 1
    assert corpus["annotations"] == []


def test_replay_orders_by_observed_at_then_stable_identity():
    corpus = append_observation({}, snapshot("2026-08-14T13:00:00+09:00"))
    corpus = append_observation(corpus, snapshot("2026-08-14T09:30:00+09:00"))
    assert [row["observed_at"] for row in replay_observations(corpus)] == [
        "2026-08-14T09:30:00+09:00",
        "2026-08-14T13:00:00+09:00",
    ]


def test_annotation_is_separate_provenanced_and_idempotent():
    corpus = append_observation({}, snapshot())
    observation_id = observation_identity(corpus["observations"][0])
    annotation = {
        "observation_id": observation_id,
        "label_source_or_authority": "owner-reviewed-validation-label",
        "annotated_at": "2026-08-14T18:00:00+09:00",
        "rationale": "Observed broad biotechnology participation; label remains evidence only.",
        "expected_signal": "candidate-strong-inflow",
    }
    corpus = append_annotation(corpus, annotation)
    corpus = append_annotation(corpus, annotation)
    assert len(corpus["annotations"]) == 1
    assert corpus["observations"][0]["flow_state"] == "UNKNOWN"


def test_annotation_missing_provenance_fails_closed():
    corpus = append_observation({}, snapshot())
    observation_id = observation_identity(corpus["observations"][0])
    with pytest.raises(ValueError, match="label_source_or_authority"):
        append_annotation(
            corpus,
            {
                "observation_id": observation_id,
                "label_source_or_authority": "",
                "annotated_at": "2026-08-14T18:00:00+09:00",
                "rationale": "missing authority must fail",
                "expected_signal": "candidate-strong-inflow",
            },
        )


def test_reversal_replay_regression_pack_v1_sequence_replay():
    """Deterministic validation corpus replay covering RISK_OFF_BROAD -> ISOLATED_RESILIENCE -> BREADTH_RECOVERY -> PARTIAL_OR_STALE."""
    # Stage 1: RISK_OFF_BROAD (09:15)
    s1 = snapshot("2026-08-14T09:15:00+09:00")
    s1["observations"] = {
        "intraday_return": -0.018,
        "benchmark_return": -0.015,
        "relative_return": -0.003,
        "rising_count": 0,
        "constituent_count": 5,
        "breadth": 0.0,
        "median_constituent_return": -0.018,
        "turnover_ratio": 1.0,
        "concentration_top1": None,
    }
    s1["leaders"] = []

    # Stage 2: ISOLATED_RESILIENCE (09:45) - single leader spikes, high concentration, narrow breadth
    s2 = snapshot("2026-08-14T09:45:00+09:00")
    s2["observations"] = {
        "intraday_return": 0.000,
        "benchmark_return": -0.010,
        "relative_return": 0.010,
        "rising_count": 1,
        "constituent_count": 5,
        "breadth": 0.2,
        "median_constituent_return": -0.010,
        "turnover_ratio": 1.5,
        "concentration_top1": 1.0,
    }
    s2["leaders"] = [{"security_code": "4588", "name": "Oncolys Bio", "intraday_return": 0.050}]

    # Stage 3: BREADTH_RECOVERY (10:30) - broad breadth recovery, lower concentration than isolated leader
    s3 = snapshot("2026-08-14T10:30:00+09:00")
    s3["observations"] = {
        "intraday_return": 0.031,
        "benchmark_return": 0.002,
        "relative_return": 0.029,
        "rising_count": 4,
        "constituent_count": 5,
        "breadth": 0.8,
        "median_constituent_return": 0.025,
        "turnover_ratio": 2.1,
        "concentration_top1": 0.48,
    }
    s3["leaders"] = [
        {"security_code": "4588", "name": "Oncolys Bio", "intraday_return": 0.077},
        {"security_code": "4592", "name": "SanBio", "intraday_return": 0.041},
    ]

    # Stage 4: PARTIAL_OR_STALE (11:30) - stale feed with partial metrics fail-closed
    s4 = snapshot("2026-08-14T11:30:00+09:00")
    s4["freshness"] = "STALE"
    s4["data_completeness"] = "PARTIAL"
    s4["observations"] = {
        "intraday_return": None,
        "benchmark_return": 0.005,
        "relative_return": None,
        "rising_count": None,
        "constituent_count": None,
        "breadth": None,
        "median_constituent_return": None,
        "turnover_ratio": None,
        "concentration_top1": None,
    }
    s4["leaders"] = []

    # Insert out-of-order to test deterministic sorting in replay
    corpus = {}
    for item in [s3, s1, s4, s2]:
        corpus = append_observation(corpus, item)

    replayed = replay_observations(corpus)
    assert len(replayed) == 4

    # Verify chronological order
    timestamps = [obs["observed_at"] for obs in replayed]
    assert timestamps == [
        "2026-08-14T09:15:00+09:00",
        "2026-08-14T09:45:00+09:00",
        "2026-08-14T10:30:00+09:00",
        "2026-08-14T11:30:00+09:00",
    ]

    # Stage 1 assertions
    r1 = replayed[0]
    assert r1["observations"]["breadth"] == 0.0
    assert r1["observations"]["concentration_top1"] is None

    # Stage 2 vs Stage 3: Isolated Leader vs Broad Recovery distinction
    r2 = replayed[1]
    r3 = replayed[2]
    assert r2["observations"]["breadth"] == 0.2
    assert r2["observations"]["concentration_top1"] == 1.0
    assert r3["observations"]["breadth"] == 0.8
    assert r3["observations"]["concentration_top1"] < r2["observations"]["concentration_top1"]

    # Stage 4: Stale/Partial fail-closed semantics
    r4 = replayed[3]
    assert r4["freshness"] == "STALE"
    assert r4["data_completeness"] == "PARTIAL"
    assert r4["observations"]["relative_return"] is None

    # All snapshots keep flow_state and acceleration_state UNKNOWN (fail-closed, no threshold changes)
    for obs in replayed:
        assert obs["flow_state"] == "UNKNOWN"
        assert obs["acceleration_state"] == "UNKNOWN"


def test_unknown_observation_reference_fails_closed():
    with pytest.raises(ValueError, match="known observation_id"):
        append_annotation(
            {"observations": [], "annotations": []},
            {
                "observation_id": "missing",
                "label_source_or_authority": "owner-reviewed-validation-label",
                "annotated_at": "2026-08-14T18:00:00+09:00",
                "rationale": "orphan labels are not replayable",
                "expected_signal": "candidate-strong-inflow",
            },
        )
