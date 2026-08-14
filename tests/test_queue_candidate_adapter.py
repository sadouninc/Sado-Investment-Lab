from scripts.queue_auto_promotion import select_next_work
from scripts.queue_candidate_adapter import build_queue_candidate


def work_contract(*, status="READY_FOR_IMPLEMENTATION", risk="GREEN"):
    return f'''```yaml
work_contract:
  version: 1
  goal: "queue candidate"
  status: {status}
  owner_slice: "adapter-slice"
  risk: {risk}
  authority: STANDARD
  dependencies: ["#479"]
  allowed_paths: ["scripts/example.py", "tests/test_example.py"]
  forbidden_paths: ["TEAM_RULES.md", "TEAM_STATE.md", ".github/**"]
  acceptance_tests: ["pytest tests/test_example.py"]
  expected_outputs: ["PR"]
  human_gate: ["merge"]
  non_goals: ["automatic dispatch"]
```'''


def issue(body=None):
    return {
        "number": 600,
        "title": "candidate",
        "state": "open",
        "body": body if body is not None else work_contract(),
    }


def test_valid_issue_reuses_preflight_and_can_be_selected():
    candidate = build_queue_candidate(
        issue(), preferred_worker="copilot", dependencies_satisfied=True, priority=1
    )
    assert candidate["preflight_valid"] is True
    assert candidate["risk"] == "GREEN"
    assert candidate["owner_slice"] == "adapter-slice"
    result = select_next_work(
        [candidate], worker_states={"copilot": "available"}
    )
    assert result["status"] == "SELECTED"
    assert result["selected"]["issue_number"] == 600


def test_invalid_contract_preserves_preflight_reasons_and_fails_closed():
    candidate = build_queue_candidate(
        issue(work_contract(status="DESIGNING")),
        preferred_worker="sora",
        dependencies_satisfied=True,
    )
    assert candidate["preflight_valid"] is False
    assert "NOT_READY" in candidate["preflight_reason_codes"]
    result = select_next_work([candidate], worker_states={"sora": "available"})
    assert result["status"] == "PREFLIGHT_INVALID"


def test_dependency_state_remains_external_and_fail_closed():
    candidate = build_queue_candidate(
        issue(), preferred_worker="sora", dependencies_satisfied=False
    )
    assert candidate["preflight_valid"] is True
    result = select_next_work([candidate], worker_states={"sora": "available"})
    assert result["status"] == "DEPENDENCY_BLOCKED"


def test_closed_issue_is_not_preflight_valid():
    closed = issue()
    closed["state"] = "closed"
    candidate = build_queue_candidate(
        closed, preferred_worker="copilot", dependencies_satisfied=True
    )
    assert candidate["preflight_valid"] is False
    assert candidate["preflight_reason_codes"] == ["ISSUE_NOT_OPEN"]
