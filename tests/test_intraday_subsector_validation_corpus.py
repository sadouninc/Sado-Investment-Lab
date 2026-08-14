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
