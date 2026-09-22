import json
from pathlib import Path

from scripts.intraday_subsector_validation_corpus import append_observation, replay_observations


FIXTURE = Path("data/fixtures/intraday-subsector-reversal-v1.json")


def replay_fixture():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    corpus = {}
    # Deliberately insert out of order: replay order, not fixture insertion order,
    # is the contract used for persistence/dropout checks.
    for row in [rows[2], rows[0], rows[4], rows[1], rows[3]]:
        corpus = append_observation(corpus, row)
    return replay_observations(corpus)


def test_replay_distinguishes_isolated_leader_from_broad_recovery_by_raw_metrics():
    replayed = replay_fixture()
    assert [row["observed_at"] for row in replayed] == [
        "2026-09-22T09:15:00+09:00",
        "2026-09-22T09:45:00+09:00",
        "2026-09-22T10:30:00+09:00",
        "2026-09-22T11:30:00+09:00",
        "2026-09-22T12:00:00+09:00",
    ]

    isolated = replayed[1]
    broad = replayed[2]
    assert isolated["observations"]["breadth"] == 0.2
    assert isolated["observations"]["rising_count"] == 1
    assert isolated["observations"]["concentration_top1"] == 0.82
    assert broad["observations"]["breadth"] == 0.8
    assert broad["observations"]["rising_count"] == 4
    assert broad["observations"]["concentration_top1"] == 0.34
    assert broad["observations"]["median_constituent_return"] > isolated["observations"]["median_constituent_return"]


def test_replay_order_exposes_leader_persistence_and_dropout_without_new_classifier():
    replayed = replay_fixture()
    isolated_codes = {leader["security_code"] for leader in replayed[1]["leaders"]}
    broad_codes = {leader["security_code"] for leader in replayed[2]["leaders"]}

    assert "4588" in isolated_codes & broad_codes
    assert "4592" in isolated_codes - broad_codes
    assert "4565" in broad_codes - isolated_codes


def test_partial_stale_and_unknown_rows_remain_fail_closed():
    replayed = replay_fixture()
    stale_partial = replayed[3]
    unknown = replayed[4]

    assert stale_partial["freshness"] == "STALE"
    assert stale_partial["data_completeness"] == "PARTIAL"
    assert stale_partial["observations"]["breadth"] is None
    assert stale_partial["observations"]["turnover_ratio"] is None
    assert stale_partial["observations"]["relative_return"] is None

    assert unknown["freshness"] == "UNKNOWN"
    assert unknown["data_completeness"] == "UNKNOWN"
    assert unknown["benchmark"] == "UNKNOWN"
    assert all(value is None for value in unknown["observations"].values())

    for row in replayed:
        assert row["flow_state"] == "UNKNOWN"
        assert row["acceleration_state"] == "UNKNOWN"
