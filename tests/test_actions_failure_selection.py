from datetime import datetime, timezone

from scripts.actions_failure_selection import select_open_pr_failure

NOW = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)
SHA = "a" * 40
SHA_NEW = "b" * 40


def pr(sha=SHA):
    return {"number": 870, "head": {"ref": "feature/870", "sha": sha}}


def run(run_id=100, conclusion="failure", sha=SHA, created="2026-10-17T23:00:00Z", attempt=1):
    return {"id": run_id, "name": "PR Preflight", "workflow_id": 10,
            "event": "pull_request", "status": "completed", "conclusion": conclusion,
            "head_branch": "feature/870", "head_sha": sha, "created_at": created,
            "run_attempt": attempt, "pull_requests": [{"number": 870}]}


def jobs():
    return [{"id": 111, "name": "preflight", "conclusion": "failure", "steps": [{"name": "pytest", "conclusion": "failure"}]}]


def choose(runs=None, prs=None, job_map=None, complete=True, job_complete=None):
    return select_open_pr_failure(
        "sadouninc/Sado-Investment-Lab", [run()] if runs is None else runs,
        [pr()] if prs is None else prs, {100: jobs()} if job_map is None else job_map,
        as_of=NOW, runs_inventory_complete=complete, prs_inventory_complete=complete,
        jobs_inventory_complete={100: True} if job_complete is None else job_complete,
    )


def test_current_open_pr_failed_job_produces_draft_only():
    result = choose()
    assert result["decision"] == "ISSUE_DRAFT_ELIGIBLE"
    assert result["analysis"]["source_run_id"] == 100
    assert result["analysis"]["error_class"] == "TEST_FAILURE"


def test_closed_or_merged_pr_failure_does_not_create_stale_issue():
    assert choose(prs=[])["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"


def test_old_head_failure_does_not_create_stale_issue():
    assert choose(prs=[pr(SHA_NEW)])["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"


def test_newer_success_supersedes_earlier_failure():
    old = run(created="2026-10-17T21:00:00Z")
    newer = run(101, "success", created="2026-10-17T23:00:00Z")
    assert choose(runs=[old, newer])["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"


def test_unrelated_newer_workflow_does_not_supersede_failure():
    other = run(101, "success")
    other["workflow_id"] = 99
    assert choose(runs=[run(), other])["decision"] == "ISSUE_DRAFT_ELIGIBLE"


def test_incomplete_inventory_fails_closed():
    assert choose(complete=False)["decision"] == "HOLD_INCOMPLETE_INVENTORY"
    assert choose(job_complete={100: False})["decision"] == "HOLD_INCOMPLETE_JOB_INVENTORY"


def test_missing_job_fails_closed():
    assert choose(job_map={}, job_complete={100: True})["decision"] == "HOLD_INCOMPLETE_JOB_INVENTORY"


def test_no_failed_job_is_not_synthetic_evidence():
    assert choose(job_map={100: [{"id": 111, "conclusion": "success"}]})["decision"] == "HOLD_NO_VERIFIED_FAILED_JOB"


def test_old_failure_outside_lookback_is_ignored():
    assert choose(runs=[run(created="2026-10-16T00:00:00Z")])["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"


def test_no_pull_request_number_with_matching_open_head_must_hold():
    bad = run()
    bad["pull_requests"] = []
    assert choose(runs=[bad])["decision"] == "HOLD_UNVERIFIED_PR_ASSOCIATION"


def test_wrong_event_is_not_eligible():
    bad = run()
    bad["event"] = "schedule"
    assert choose(runs=[bad])["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"


def test_latest_failed_run_needs_complete_jobs_even_if_older_complete():
    later = run(101, created="2026-10-17T23:30:00Z")
    assert choose(runs=[run(), later], job_complete={100: True})["decision"] == "HOLD_INCOMPLETE_JOB_INVENTORY"


def test_newer_in_progress_same_workflow_blocks_stale_failure():
    older = run(100, "failure", created="2026-10-17T21:00:00Z")
    newer = run(101, "failure", created="2026-10-17T23:00:00Z")
    newer["status"] = "in_progress"
    newer["conclusion"] = None
    assert choose(runs=[older, newer])["decision"] == "HOLD_PENDING_CURRENT_HEAD_RUN"


def test_newer_queued_same_workflow_blocks_stale_failure():
    older = run(100, "failure", created="2026-10-17T21:00:00Z")
    newer = run(101, "failure", created="2026-10-17T23:00:00Z")
    newer["status"] = "queued"
    newer["conclusion"] = None
    assert choose(runs=[older, newer])["decision"] == "HOLD_PENDING_CURRENT_HEAD_RUN"


def test_pending_run_does_not_hide_independent_workflow_failure():
    older = run()
    unrelated = run(101, created="2026-10-17T23:30:00Z")
    unrelated["workflow_id"] = 77
    unrelated["status"] = "in_progress"
    unrelated["conclusion"] = None
    assert choose(runs=[older, unrelated])["decision"] == "ISSUE_DRAFT_ELIGIBLE"


def test_unknown_status_fails_closed():
    bad = run()
    bad["status"] = "unknown_new_status"
    assert choose(runs=[bad])["decision"] == "HOLD_INVALID_RUN_INVENTORY"


def test_unassociated_run_without_matching_open_pr_does_not_block():
    bad = run()
    bad["pull_requests"] = []
    assert choose(runs=[bad], prs=[{"number": 870, "head": {"ref": "other-branch", "sha": SHA}}])["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"


def test_unassociated_pending_current_head_must_hold():
    pending = run()
    pending["pull_requests"] = []
    pending["status"] = "in_progress"
    pending["conclusion"] = None
    assert choose(runs=[pending])["decision"] == "HOLD_UNVERIFIED_PR_ASSOCIATION"


def test_unassociated_success_is_not_failure():
    success = run(conclusion="success")
    success["pull_requests"] = []
    assert choose(runs=[success])["decision"] == "NO_CURRENT_OPEN_PR_FAILURE"
