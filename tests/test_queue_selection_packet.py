import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.queue_selection_packet import build_candidates, build_selection_packet, main

ROOT = Path(__file__).resolve().parents[1]


def work_contract(*, status="READY_FOR_IMPLEMENTATION", risk="GREEN", owner_slice="pkt-slice"):
    return f'''```yaml
work_contract:
  version: 1
  goal: "queue selection packet"
  status: {status}
  owner_slice: "{owner_slice}"
  risk: {risk}
  authority: STANDARD
  dependencies: ["#556"]
  allowed_paths: ["scripts/example.py"]
  forbidden_paths: ["TEAM_RULES.md", "TEAM_STATE.md", ".github/**"]
  acceptance_tests: ["pytest tests/test_example.py"]
  expected_outputs: ["PR"]
  human_gate: ["merge"]
  non_goals: ["automatic dispatch"]
```'''


def issue(number=600, *, body=None, state="open", owner_slice="pkt-slice"):
    return {
        "number": number,
        "title": f"candidate {number}",
        "state": state,
        "body": body if body is not None else work_contract(owner_slice=owner_slice),
    }


def test_valid_green_candidate_is_selected_alone():
    packet = build_selection_packet(
        [issue(600)],
        assignments={"600": {"preferred_worker": "copilot", "dependencies_satisfied": True, "priority": 1}},
        worker_states={"copilot": "available"},
    )
    assert packet["status"] == "SELECTED"
    assert packet["selected"]["issue_number"] == 600
    assert len(packet["candidates"]) == 1


def test_invalid_non_ready_contract_is_preflight_invalid():
    packet = build_selection_packet(
        [issue(601, body=work_contract(status="DESIGNING"))],
        assignments={"601": {"preferred_worker": "copilot", "dependencies_satisfied": True}},
        worker_states={"copilot": "available"},
    )
    assert packet["status"] == "PREFLIGHT_INVALID"
    assert packet["selected"] is None


def test_quota_blocked_worker_is_not_selected():
    packet = build_selection_packet(
        [issue(602)],
        assignments={"602": {"preferred_worker": "kai", "dependencies_satisfied": True}},
        worker_states={"kai": "quota_blocked"},
    )
    assert packet["status"] == "WORKER_BLOCKED"
    assert packet["selected"] is None


def test_dependency_false_is_dependency_blocked():
    packet = build_selection_packet(
        [issue(603)],
        assignments={"603": {"preferred_worker": "copilot", "dependencies_satisfied": False}},
        worker_states={"copilot": "available"},
    )
    assert packet["status"] == "DEPENDENCY_BLOCKED"
    assert packet["selected"] is None


def test_missing_assignment_defaults_to_dependency_blocked_fail_closed():
    packet = build_selection_packet(
        [issue(604)],
        assignments={},
        worker_states={"copilot": "available", "unassigned": "available"},
    )
    assert packet["status"] == "DEPENDENCY_BLOCKED"


def test_owner_path_conflict_is_excluded():
    packet = build_selection_packet(
        [issue(605, owner_slice="busy-slice")],
        assignments={"605": {"preferred_worker": "copilot", "dependencies_satisfied": True}},
        worker_states={"copilot": "available"},
        active_owner_slices=["busy-slice"],
    )
    assert packet["status"] == "OWNER_CONFLICT"
    assert packet["selected"] is None
    assert packet["metrics"]["duplicate_start_prevented_count"] == 1


def test_same_input_produces_same_output_deterministically():
    issues = [issue(607, owner_slice="a"), issue(606, owner_slice="b")]
    assignments = {
        "606": {"preferred_worker": "copilot", "dependencies_satisfied": True, "priority": 2},
        "607": {"preferred_worker": "copilot", "dependencies_satisfied": True, "priority": 1},
    }
    first = build_selection_packet(issues, assignments=assignments, worker_states={"copilot": "available"})
    second = build_selection_packet(
        list(reversed(issues)), assignments=assignments, worker_states={"copilot": "available"}
    )
    assert first == second
    assert first["status"] == "SELECTED"
    assert first["selected"]["issue_number"] == 607


def test_candidates_are_built_via_existing_adapter_in_sorted_order():
    candidates = build_candidates(
        [issue(609), issue(608)],
        {
            "608": {"preferred_worker": "copilot", "dependencies_satisfied": True},
            "609": {"preferred_worker": "copilot", "dependencies_satisfied": True},
        },
    )
    assert [row["issue_number"] for row in candidates] == [608, 609]
    assert all("preflight_valid" in row for row in candidates)


def test_no_github_writes_are_imported_or_performed():
    source = (ROOT / "scripts" / "queue_selection_packet.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "PyGithub", "github3", "gh api", "subprocess"):
        assert forbidden not in source


def test_cli_prints_deterministic_json_and_writes_output_file():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        issues_path = root / "issues.json"
        worker_state_path = root / "worker_state.json"
        assignments_path = root / "assignments.json"
        output_path = root / "packet.json"

        issues_path.write_text(json.dumps([issue(610)]), encoding="utf-8")
        worker_state_path.write_text(json.dumps({"copilot": "available"}), encoding="utf-8")
        assignments_path.write_text(
            json.dumps({"610": {"preferred_worker": "copilot", "dependencies_satisfied": True}}),
            encoding="utf-8",
        )

        exit_code = main(
            [
                "--issues",
                str(issues_path),
                "--worker-state",
                str(worker_state_path),
                "--assignments",
                str(assignments_path),
                "--output",
                str(output_path),
            ]
        )
        assert exit_code == 0
        packet = json.loads(output_path.read_text(encoding="utf-8"))
        assert packet["status"] == "SELECTED"
        assert packet["selected"]["issue_number"] == 610


def test_cli_returns_nonzero_exit_when_not_selected():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        issues_path = root / "issues.json"
        worker_state_path = root / "worker_state.json"

        issues_path.write_text(json.dumps([issue(611)]), encoding="utf-8")
        worker_state_path.write_text(json.dumps({"copilot": "available"}), encoding="utf-8")

        exit_code = main(["--issues", str(issues_path), "--worker-state", str(worker_state_path)])
        assert exit_code == 1


def test_cli_subprocess_runs_read_only_with_no_network_dependency():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        issues_path = root / "issues.json"
        worker_state_path = root / "worker_state.json"
        assignments_path = root / "assignments.json"

        issues_path.write_text(json.dumps([issue(612)]), encoding="utf-8")
        worker_state_path.write_text(json.dumps({"copilot": "available"}), encoding="utf-8")
        assignments_path.write_text(
            json.dumps({"612": {"preferred_worker": "copilot", "dependencies_satisfied": True}}),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.queue_selection_packet",
                "--issues",
                str(issues_path),
                "--worker-state",
                str(worker_state_path),
                "--assignments",
                str(assignments_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        packet = json.loads(completed.stdout)
        assert packet["status"] == "SELECTED"
        assert packet["selected"]["issue_number"] == 612
