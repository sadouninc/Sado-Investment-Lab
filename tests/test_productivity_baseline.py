import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_productivity_baseline",
    ROOT / "scripts" / "build_productivity_baseline.py",
)
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def load_payload():
    with open(
        ROOT / "tests" / "fixtures" / "productivity_baseline_v1.json",
        "r",
        encoding="utf-8",
    ) as source:
        return json.load(source)


def test_baseline_is_deterministic_and_has_required_case_mix():
    payload = load_payload()
    first = baseline.build_dataset(payload)
    second = baseline.build_dataset(payload)
    assert first == second
    assert len(first) == 4
    assert {item["case_class"] for item in first} == {
        "STALE_BASE_MERGE_CONFLICT",
        "DUPLICATE_WORK_OWNER_CONFLICT",
        "FALSE_READY_HARNESS_GAP",
        "NORMAL_LOW_RISK_CONTROL",
    }


def test_historical_cases_use_only_explicit_evidence():
    records = {item["case_id"]: item for item in baseline.build_dataset(load_payload())}

    stale = records["stale-base-472"]["telemetry"]
    assert stale["blockers"] == ["merge_conflict", "superseded"]
    assert stale["result"] == "UNKNOWN"
    assert all(value is None for value in stale["timestamps"].values())

    duplicate = records["duplicate-owner-475"]["telemetry"]
    assert duplicate["blockers"] == ["superseded"]
    assert duplicate["metrics"]["clarification_count"] == 0
    assert duplicate["metrics"]["human_confirmation_count"] == 0
    assert duplicate["metrics"]["review_rework_count"] == 0

    false_ready = records["false-ready-483"]["telemetry"]
    assert false_ready["metrics"]["false_ready_count"] == 1
    assert false_ready["timestamps"]["pr_review_ready_at"] is None


def test_normal_control_does_not_invent_blockers_or_rework():
    records = {item["case_id"]: item for item in baseline.build_dataset(load_payload())}
    control = records["normal-control-504"]["telemetry"]
    assert control["blockers"] == []
    assert control["metrics"]["conflict_count"] == 0
    assert control["metrics"]["review_rework_count"] == 0
    assert control["metrics"]["ci_rework_count"] == 0
    assert control["metrics"]["first_pass_ci"] == "PASS"


def test_tracked_jsonl_matches_fixture_projection():
    expected = baseline.build_dataset(load_payload())
    with open(
        ROOT / "data" / "generated" / "diagnostics" / "productivity_baseline_v1.jsonl",
        "r",
        encoding="utf-8",
    ) as source:
        actual = [json.loads(line) for line in source if line.strip()]
    assert actual == expected


def test_invalid_explicit_result_fails_closed():
    case = {
        "case_id": "bad",
        "case_class": "BAD",
        "evidence_quality": "UNKNOWN",
        "source_refs": [],
        "explicit_result": "ASSUMED_MERGED",
        "event": {},
    }
    try:
        baseline.build_case(case)
    except ValueError as error:
        assert "unsupported explicit_result" in str(error)
    else:
        raise AssertionError("invalid explicit result must fail closed")
