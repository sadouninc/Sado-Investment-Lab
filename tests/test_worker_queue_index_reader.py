import json
import subprocess
import sys
from pathlib import Path

from scripts.worker_queue_index_reader import (
    STATUS_UNVERIFIED,
    STATUS_VERIFIED,
    build_report,
    extract_index_payloads,
    main,
    validate_index,
)

ROOT = Path(__file__).resolve().parents[1]


def index(revision=1, *, authority="LUNA", workers=None, broadcast_head=500, **extra):
    payload = {
        "schema": "worker_queue_index_v1",
        "revision": revision,
        "authority": authority,
        "as_of": "2099-01-01",
        "broadcast_head": broadcast_head,
        "semantics": "discovery_only",
        "workers": workers
        if workers is not None
        else {
            "ALPHA": {
                "review_prs": [10],
                "now": [{"issue": 101, "state": "READY_FOR_IMPLEMENTATION"}],
                "next": [{"issue": 102, "state": "READY_FOR_IMPLEMENTATION"}],
                "reserve": [{"issue": 103, "state": "DEPENDENCY_HOLD"}],
            },
            "BETA": {"review_prs": [], "now": [{"issue": 201, "state": "IMPLEMENTING"}], "next": [], "reserve": []},
        },
    }
    payload.update(extra)
    return payload


def comment(cid, payload=None, *, text=None, login="synthetic-bot"):
    if text is None:
        text = f"Flow note\nWORKER_QUEUE_INDEX_V1 revision {payload['revision']}.\n```json\n{json.dumps(payload, indent=2)}\n```\n"
    return {"id": cid, "created_at": f"2099-01-01T00:00:{cid % 60:02d}Z", "user": {"login": login}, "body": text}


def plain(cid, text="ordinary comment"):
    return {"id": cid, "created_at": "2099-01-01T00:00:00Z", "user": {"login": "x"}, "body": text}


def report(comments, worker="ALPHA", count="auto", **kw):
    if count == "auto":
        count = len(comments)
    return build_report(comments, worker=worker, expected_comment_count=count, **kw)


def test_normal_selects_latest_revision_for_explicit_worker():
    comments = [plain(1), comment(2, index(1)), plain(3), comment(4, index(2)), plain(5)]
    r = report(comments, expected_last_comment_id=5, expected_broadcast_head=500)
    assert r["status"] == STATUS_VERIFIED
    assert r["blockers"] == []
    assert r["source"]["index_comment_id"] == 4
    assert r["source"]["index_revision"] == 2
    assert r["queue"]["review_prs"] == [10]
    assert [i["issue"] for i in r["queue"]["now"]] == [101]
    assert r["queue"]["reserve"][0]["not_ready_by_index"] is True
    assert r["queue"]["now"][0]["not_ready_by_index"] is False
    assert all(i["pointer_only"] for lane in ("now", "next", "reserve") for i in r["queue"][lane])
    assert r["grants_authority"] is False
    assert r["ready_determination"] == "not_performed"
    assert any("not authenticated" in limit for limit in r["evidence_limits"])


def test_report_is_deterministic():
    comments = [comment(2, index(1)), comment(4, index(2))]
    assert json.dumps(report(comments), sort_keys=True) == json.dumps(report(comments), sort_keys=True)


def test_missing_comment_count_is_unverified():
    r = report([comment(2, index(1))], count=None)
    assert r["status"] == STATUS_UNVERIFIED
    assert r["queue"] is None
    assert any("expected comment count not supplied" in b for b in r["blockers"])


def test_partial_page_is_unverified_not_empty():
    r = report([comment(2, index(1))], count=150)
    assert r["status"] == STATUS_UNVERIFIED
    assert any("fetched 1 comments, issue reports 150" in b for b in r["blockers"])


def test_last_comment_id_mismatch_is_unverified():
    r = report([comment(2, index(1)), plain(3)], expected_last_comment_id=9)
    assert r["status"] == STATUS_UNVERIFIED


def test_duplicate_comment_ids_from_pagination_overlap():
    c = comment(2, index(1))
    r = report([c, c])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("duplicate comment ids" in b for b in r["blockers"])


def test_out_of_order_comments_rejected():
    r = report([comment(4, index(2)), comment(2, index(1))])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("ascending" in b for b in r["blockers"])


def test_no_index_found():
    r = report([plain(1), plain(2)])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("no valid" in b for b in r["blockers"])


def test_malformed_json_block_is_ignored_with_warning_and_fails_closed_alone():
    bad = plain(2, "WORKER_QUEUE_INDEX_V1\n```json\n{\"schema\": \"worker_queue_index_v1\", \n```")
    r = report([bad])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("payload is not a JSON object" in w for w in r["warnings"])


def test_marker_without_block_warns():
    r = report([plain(2, "WORKER_QUEUE_INDEX_V1 mentioned in prose"), comment(3, index(1))])
    assert r["status"] == STATUS_VERIFIED
    assert any("marker without" in w for w in r["warnings"])


def test_unauthorized_authority_is_not_selected():
    r = report([comment(2, index(1)), comment(3, index(2, authority="SORA"))])
    # revision 2 from a non-authority is ignored, revision 1 from LUNA stays selected
    assert r["status"] == STATUS_VERIFIED
    assert r["source"]["index_revision"] == 1
    assert any("not an allowed Flow Authority" in w for w in r["warnings"])


def test_worker_identity_is_exact_not_inferred():
    for name in ("alpha", "ALPHA_SCHEDULED", "GAMMA"):
        r = report([comment(2, index(1))], worker=name)
        assert r["status"] == STATUS_UNVERIFIED
        assert r["queue"] is None
        assert any("not present in index" in b for b in r["blockers"])


def test_conflicting_same_revision():
    other = index(2, workers={"ALPHA": {"review_prs": [], "now": [], "next": [], "reserve": []}})
    r = report([comment(2, index(2)), comment(3, other)])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("conflicting content" in b for b in r["blockers"])


def test_identical_repost_of_same_revision_is_fine():
    r = report([comment(2, index(2)), comment(3, index(2))])
    assert r["status"] == STATUS_VERIFIED
    assert r["source"]["index_comment_id"] == 3


def test_revision_regression_is_ambiguous():
    r = report([comment(2, index(3)), comment(3, index(2))])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("regression" in b for b in r["blockers"])


def test_issue_assigned_to_two_workers():
    workers = {
        "ALPHA": {"review_prs": [], "now": [{"issue": 7, "state": "READY_FOR_IMPLEMENTATION"}], "next": [], "reserve": []},
        "BETA": {"review_prs": [], "now": [], "next": [{"issue": 7, "state": "READY_FOR_IMPLEMENTATION"}], "reserve": []},
    }
    r = report([comment(2, index(1, workers=workers))])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("multiple workers" in b for b in r["blockers"])


def test_issue_listed_twice_for_one_worker():
    workers = {
        "ALPHA": {
            "review_prs": [],
            "now": [{"issue": 7, "state": "READY_FOR_IMPLEMENTATION"}],
            "next": [],
            "reserve": [{"issue": 7, "state": "READY_FOR_IMPLEMENTATION"}],
        }
    }
    r = report([comment(2, index(1, workers=workers))])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("more than once" in b for b in r["blockers"])


def test_stale_broadcast_head():
    r = report([comment(2, index(1, broadcast_head=499))], expected_broadcast_head=500)
    assert r["status"] == STATUS_UNVERIFIED
    assert any("broadcast_head" in b for b in r["blockers"])


def test_two_blocks_in_one_comment():
    text = (
        "WORKER_QUEUE_INDEX_V1\n```json\n" + json.dumps(index(1)) + "\n```\n```json\n" + json.dumps(index(2)) + "\n```"
    )
    r = report([plain(2, text)])
    assert r["status"] == STATUS_UNVERIFIED
    assert any("multiple index JSON blocks" in b for b in r["blockers"])


def test_validate_index_boundaries():
    assert validate_index(index(1), ["LUNA"]) == []
    assert validate_index([], ["LUNA"]) == ["payload is not a JSON object"]
    assert any("revision" in p for p in validate_index(index(0), ["LUNA"]))
    assert any("revision" in p for p in validate_index(index(True), ["LUNA"]))
    assert any("semantics" in p for p in validate_index(index(1, semantics="authorization"), ["LUNA"]))
    assert any("workers" in p for p in validate_index(index(1, workers={}), ["LUNA"]))
    bad_item = index(1, workers={"A": {"review_prs": ["10"], "now": [{"issue": "1", "state": ""}]}})
    problems = validate_index(bad_item, ["LUNA"])
    assert any("review_prs" in p for p in problems)
    assert any(".issue" in p for p in problems)
    assert any(".state" in p for p in problems)


def test_extract_ignores_unrelated_json_blocks():
    body = "```json\n{\"other\": 1}\n```\n```json\n" + json.dumps(index(1)) + "\n```"
    assert [p["revision"] for p in extract_index_payloads(body)] == [1]


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps([plain(1), comment(2, index(1))]), encoding="utf-8")
    out = tmp_path / "report.json"
    assert main(["--comments", str(good), "--worker", "ALPHA", "--expected-comment-count", "2", "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == STATUS_VERIFIED
    assert main(["--comments", str(good), "--worker", "ALPHA"]) == 1
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert main(["--comments", str(broken), "--worker", "ALPHA"]) == 2
    notlist = tmp_path / "notlist.json"
    notlist.write_text("{}", encoding="utf-8")
    assert main(["--comments", str(notlist), "--worker", "ALPHA"]) == 2


def test_cli_runs_as_module(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps([comment(2, index(1))]), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.worker_queue_index_reader", "--comments", str(good), "--worker", "BETA",
         "--expected-comment-count", "1"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["queue"]["now"][0]["issue"] == 201
