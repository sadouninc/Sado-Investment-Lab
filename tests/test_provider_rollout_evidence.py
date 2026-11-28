import copy
import json
import subprocess
import sys
from pathlib import Path

from scripts.provider_rollout_evidence import STATUS_COMPLETE, STATUS_HOLD, build_report, main

ROOT = Path(__file__).resolve().parents[1]


def sha(ch):
    return ch * 40


TARGET_HEAD = sha("a")
DEP_HEAD = sha("b")
DEP_MERGE = sha("c")
BASE = sha("d")


def snapshot():
    return {
        "target": {"pr": 20, "head_sha": TARGET_HEAD},
        "dependencies": [{"pr": 10, "provider": "events"}],
        "prs": [
            {"number": 10, "state": "closed", "merged": True, "head_sha": DEP_HEAD, "merge_commit_sha": DEP_MERGE},
            {"number": 20, "state": "open", "merged": False, "head_sha": TARGET_HEAD},
        ],
        "ci": {
            "head_sha": TARGET_HEAD,
            "required_checks": ["build", "preflight"],
            "checks": [
                {"name": "build", "conclusion": "success"},
                {"name": "preflight", "conclusion": "success"},
                {"name": "deploy", "conclusion": "skipped"},
            ],
        },
        "integration": {
            "base_sha": BASE,
            "refs": [{"pr": 10, "sha": DEP_MERGE}, {"pr": 20, "sha": TARGET_HEAD}],
            "passed": 9,
            "failed": 0,
            "errors": 0,
        },
    }


def codes(report):
    return {r["code"] for r in report["hold_reasons"]}


def test_complete_evidence():
    r = build_report(snapshot())
    assert r["status"] == STATUS_COMPLETE, r["hold_reasons"]
    assert r["hold_reasons"] == []
    assert r["merge_authorized"] is False
    assert r["dependencies"] == [{"pr": 10, "provider": "events", "merged": True, "merge_commit_sha": DEP_MERGE}]
    assert any("not a review" in limit for limit in r["evidence_limits"])


def test_dependency_final_head_is_accepted_in_integration():
    s = snapshot()
    s["integration"]["refs"][0]["sha"] = DEP_HEAD
    assert build_report(s)["status"] == STATUS_COMPLETE


def test_deterministic():
    assert json.dumps(build_report(snapshot()), sort_keys=True) == json.dumps(build_report(snapshot()), sort_keys=True)


def test_merge_authorized_false_even_when_complete_and_when_hold():
    assert build_report(snapshot())["merge_authorized"] is False
    assert build_report({})["merge_authorized"] is False


def test_dependency_not_merged_holds():
    s = snapshot()
    s["prs"][0].update({"merged": False, "state": "open", "merge_commit_sha": None})
    s["integration"]["refs"][0]["sha"] = DEP_HEAD
    r = build_report(s)
    assert r["status"] == STATUS_HOLD
    assert "DEPENDENCY_NOT_MERGED" in codes(r)


def test_dependency_snapshot_missing_holds():
    s = snapshot()
    del s["prs"][0]
    assert "DEPENDENCY_SNAPSHOT_MISSING" in codes(build_report(s))


def test_merged_without_merge_sha_is_malformed():
    s = snapshot()
    s["prs"][0]["merge_commit_sha"] = "abc"
    assert "MALFORMED" in codes(build_report(s))


def test_integration_used_old_dependency_head():
    s = snapshot()
    s["integration"]["refs"][0]["sha"] = sha("e")
    assert "STALE_DEPENDENCY_REF" in codes(build_report(s))


def test_integration_missing_dependency_ref():
    s = snapshot()
    s["integration"]["refs"] = [{"pr": 20, "sha": TARGET_HEAD}]
    assert "INTEGRATION_REF_MISSING" in codes(build_report(s))


def test_integration_ran_old_target_head():
    s = snapshot()
    s["integration"]["refs"][1]["sha"] = sha("f")
    assert "STALE_TARGET_HEAD" in codes(build_report(s))


def test_target_snapshot_head_moved():
    s = snapshot()
    s["prs"][1]["head_sha"] = sha("9")
    assert "STALE_TARGET_HEAD" in codes(build_report(s))


def test_target_already_merged():
    s = snapshot()
    s["prs"][1]["merged"] = True
    assert "TARGET_ALREADY_MERGED" in codes(build_report(s))


def test_integration_failures_and_zero_passed():
    for change in ({"failed": 2}, {"errors": 1}, {"passed": 0}):
        s = snapshot()
        s["integration"].update(change)
        assert "INTEGRATION_NOT_GREEN" in codes(build_report(s)), change


def test_integration_counts_must_be_ints():
    for bad in (True, -1, "9", None, 9.0):
        s = snapshot()
        s["integration"]["passed"] = bad
        assert "MALFORMED" in codes(build_report(s)), bad


def test_integration_missing():
    s = snapshot()
    del s["integration"]
    assert "INTEGRATION_MISSING" in codes(build_report(s))


def test_conflicting_integration_ref():
    s = snapshot()
    s["integration"]["refs"].append({"pr": 10, "sha": sha("e")})
    assert "CONFLICTING_INTEGRATION_REF" in codes(build_report(s))


def test_ci_for_other_head():
    s = snapshot()
    s["ci"]["head_sha"] = sha("1")
    assert "STALE_CI_HEAD" in codes(build_report(s))


def test_ci_required_check_failed_missing_or_contradictory():
    s = snapshot()
    s["ci"]["checks"][0]["conclusion"] = "failure"
    r = build_report(s)
    assert "CI_NOT_GREEN" in codes(r)
    assert r["ci"]["missing_or_failed"] == ["build"]

    s = snapshot()
    s["ci"]["checks"] = s["ci"]["checks"][1:]
    assert build_report(s)["ci"]["missing_or_failed"] == ["build"]

    s = snapshot()
    s["ci"]["checks"].append({"name": "build", "conclusion": "failure"})
    assert "CI_NOT_GREEN" in codes(build_report(s))


def test_ci_missing_or_empty_required():
    s = snapshot()
    del s["ci"]
    assert "CI_MISSING" in codes(build_report(s))
    s = snapshot()
    s["ci"]["required_checks"] = []
    assert "MALFORMED" in codes(build_report(s))


def test_duplicate_and_conflicting_snapshots():
    s = snapshot()
    s["prs"].append(copy.deepcopy(s["prs"][0]))
    assert "DUPLICATE_SNAPSHOT" in codes(build_report(s))
    s = snapshot()
    other = copy.deepcopy(s["prs"][0])
    other["merged"] = False
    s["prs"].append(other)
    assert "CONFLICTING_SNAPSHOT" in codes(build_report(s))


def test_duplicate_dependency_and_self_dependency():
    s = snapshot()
    s["dependencies"].append({"pr": 10})
    assert "DUPLICATE_DEPENDENCY" in codes(build_report(s))
    s = snapshot()
    s["dependencies"].append({"pr": 20})
    assert "MALFORMED" in codes(build_report(s))


def test_multiple_dependencies_each_checked():
    s = snapshot()
    s["dependencies"].append({"pr": 11, "provider": "market"})
    r = build_report(s)
    assert "DEPENDENCY_SNAPSHOT_MISSING" in codes(r)
    s["prs"].append({"number": 11, "merged": True, "head_sha": sha("2"), "merge_commit_sha": sha("3")})
    assert "INTEGRATION_REF_MISSING" in codes(build_report(s))
    s["integration"]["refs"].append({"pr": 11, "sha": sha("3")})
    assert build_report(s)["status"] == STATUS_COMPLETE


def test_malformed_documents_never_raise():
    for doc in (None, [], "x", 1, {"target": "x", "dependencies": "y", "prs": "z", "ci": [], "integration": 3},
                {"target": {"pr": True, "head_sha": TARGET_HEAD}}, {"target": {"pr": 1, "head_sha": "A" * 40}}):
        r = build_report(doc)
        assert r["status"] == STATUS_HOLD
        assert r["merge_authorized"] is False


def test_empty_dependencies_hold():
    s = snapshot()
    s["dependencies"] = []
    assert "MALFORMED" in codes(build_report(s))


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(snapshot()), encoding="utf-8")
    out = tmp_path / "out.json"
    assert main(["--snapshot", str(good), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == STATUS_COMPLETE
    held = tmp_path / "held.json"
    s = snapshot()
    s["prs"][0]["merged"] = False
    held.write_text(json.dumps(s), encoding="utf-8")
    assert main(["--snapshot", str(held)]) == 1
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    assert main(["--snapshot", str(broken)]) == 2


def test_cli_runs_as_module(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(snapshot()), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.provider_rollout_evidence", "--snapshot", str(good)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["merge_authorized"] is False
