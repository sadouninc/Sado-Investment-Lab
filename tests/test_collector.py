import importlib.util
import json
import pathlib

spec = importlib.util.spec_from_file_location(
    "telemetry_collector",
    str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "telemetry_collector.py"),
)
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)


def load_fixture(name):
    with open(f"tests/fixtures/{name}", "r", encoding="utf-8") as source:
        return json.load(source)


def test_basic_fixture():
    record = tc.collect_from_fixture(load_fixture("fixture_basic.json"))
    assert record == {
        "schema_version": 1,
        "unit_type": "PR",
        "issue_ref": "repo#122",
        "pr_ref": "repo#123",
        "actor": "alice",
        "lane": "NOW",
        "risk": "low",
        "timestamps": {
            "issue_ready_at": "2026-06-30T09:00:00Z",
            "implementation_started_at": "2026-07-01T09:00:00Z",
            "pr_created_at": "2026-07-01T12:00:00Z",
            "pr_review_ready_at": "2026-07-02T10:00:00Z",
            "pr_merged_at": "2026-07-03T15:00:00Z",
        },
        "metrics": {
            "clarification_count": 1,
            "human_confirmation_count": 1,
            "review_rework_count": 1,
            "ci_rework_count": 1,
            "conflict_count": 1,
            "false_ready_count": 0,
            "first_pass_ci": "FAIL",
        },
        "blockers": ["merge_conflict"],
        "result": "MERGED",
        "evidence_refs": ["repo#123", "repo#122"],
    }


def test_missing_evidence_is_unknown_not_inferred():
    record = tc.collect_from_fixture({})
    assert all(value is None for value in record["timestamps"].values())
    assert record["metrics"] == {
        "clarification_count": 0,
        "human_confirmation_count": 0,
        "review_rework_count": 0,
        "ci_rework_count": 0,
        "conflict_count": 0,
        "false_ready_count": 0,
        "first_pass_ci": "UNKNOWN",
    }
    assert record["result"] == "UNKNOWN"
    assert record["blockers"] == []


def test_reviews_and_nonterminal_ci_do_not_create_other_metrics():
    event = {
        "pr_ref": "repo#200",
        "reviews": [
            {"round_id": "review-1", "event": "CHANGES_REQUESTED"},
            {"event": "APPROVED"},
        ],
        "ci_runs": [
            {"status": "queued"},
            {"status": "in_progress"},
            {"status": "skipped"},
            {"status": "cancelled"},
            {"status": "neutral"},
        ],
    }
    metrics = tc.collect_from_fixture(event)["metrics"]
    assert metrics["clarification_count"] == 0
    assert metrics["human_confirmation_count"] == 0
    assert metrics["review_rework_count"] == 0
    assert metrics["ci_rework_count"] == 0
    assert metrics["first_pass_ci"] == "UNKNOWN"


def test_review_rework_counts_only_rounds_with_explicit_fix_evidence():
    reviews = [
        {"round_id": "round-1", "event": "CHANGES_REQUESTED"},
        {"round_id": "round-2", "event": "CHANGES_REQUESTED"},
        {"round_id": "round-3", "event": "CHANGES_REQUESTED"},
    ]
    fixes = [
        {"round_id": "round-1", "evidence_ref": "commit-a"},
        {"round_id": "round-1", "evidence_ref": "commit-a-duplicate"},
        {"round_id": "round-3", "evidence_ref": "commit-c"},
        {"round_id": "unknown-round", "evidence_ref": "commit-x"},
        {"round_id": "round-2"},
    ]
    assert tc.count_review_rework(reviews, fixes) == 2
    assert tc.count_review_rework(reviews, []) == 0


def test_ci_rework_counts_closed_failure_episode_only():
    assert tc.count_ci_rework([
        {"status": "queued"},
        {"status": "failure"},
        {"status": "failure"},
        {"status": "in_progress"},
        {"status": "success"},
    ]) == 1
    assert tc.count_ci_rework([{"status": "failure"}]) == 0


def test_blocker_taxonomy_and_false_ready_marker():
    event = {
        "conflicts": ["stale base", "merge conflict", "superseded"],
        "markers": [{"name": "FALSE_READY", "at": "2026-07-01T00:00:00Z"}],
    }
    record = tc.collect_from_fixture(event)
    assert record["blockers"] == ["merge_conflict", "superseded"]
    assert record["metrics"]["conflict_count"] == 3
    assert record["metrics"]["false_ready_count"] == 1


def test_sample_artifact_matches_basic_fixture():
    expected = tc.collect_from_fixture(load_fixture("fixture_basic.json"))
    with open(
        "data/generated/diagnostics/sample_telemetry.jsonl",
        "r",
        encoding="utf-8",
    ) as source:
        sample = json.loads(source.readline())
    assert sample == expected
