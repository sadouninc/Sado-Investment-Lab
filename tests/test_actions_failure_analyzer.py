from scripts.actions_failure_analyzer import (
    analyze_completed_failure,
    build_issue_draft,
    decide_issue_action,
)


def run(**changes):
    result = {"id": 1234, "name": "CI", "status": "completed", "conclusion": "failure", "created_at": "2026-10-18T00:00:00Z"}
    result.update(changes)
    return result


def jobs(step="pytest"):
    return [{"id": 5678, "name": "test", "conclusion": "failure", "steps": [{"name": step, "conclusion": "failure"}]}]


def analyze(r=None, j=None):
    return analyze_completed_failure("owner/repo", run() if r is None else r, jobs() if j is None else j)


def test_completed_real_failure_is_classified_with_traceable_evidence():
    item = analyze()
    assert item["error_class"] == "TEST_FAILURE"
    assert item["source_run_id"] == 1234 and item["job_id"] == 5678
    assert item["reproduction_evidence"] == "https://github.com/owner/repo/actions/runs/1234/job/5678"
    assert item["candidate_root_cause"].startswith("HYPOTHESIS:")


def test_success_and_in_progress_are_not_anomalies():
    assert analyze(run(conclusion="success")) is None
    assert analyze(run(status="in_progress")) is None


def test_missing_failed_jobs_does_not_invent_failure():
    assert analyze(j=[{"id": 12, "conclusion": "success"}]) is None


def test_same_run_classification_produces_stable_request_id():
    assert analyze()["request_id"] == analyze()["request_id"]


def test_duplicate_suppressed_and_incomplete_inventory_held():
    item = analyze()
    draft = build_issue_draft(item)
    assert decide_issue_action(item, [{"number": 42, "body": draft["body"]}], inventory_complete=True) == "DUPLICATE_SUPPRESSED"
    assert decide_issue_action(item, [], inventory_complete=False) == "HOLD_INCOMPLETE_ISSUE_INVENTORY"


def test_issue_79_is_never_targeted_and_draft_is_not_ready():
    item = analyze()
    assert decide_issue_action(item, [{"number": 79, "body": "irrelevant"}], inventory_complete=True) == "ISSUE_DRAFT_ELIGIBLE"
    draft = build_issue_draft(item)
    assert "READY_FOR_IMPLEMENTATIONには自動昇格しない" in draft["body"]
    assert "#79変更禁止" in draft["body"]


def test_untrusted_step_name_is_sanitized():
    item = analyze(j=jobs("pytest\n<malicious>`|"))
    assert "<" not in item["failing_step"] and "\n" not in item["failing_step"]


def test_invalid_repository_and_identifiers_are_rejected():
    import pytest
    with pytest.raises(ValueError):
        analyze_completed_failure("invalid", run(), jobs())
    with pytest.raises(ValueError):
        analyze(run(id=-2))


def test_no_failure_requires_no_issue():
    assert decide_issue_action(None, [], inventory_complete=True) == "NO_FAILURE"
