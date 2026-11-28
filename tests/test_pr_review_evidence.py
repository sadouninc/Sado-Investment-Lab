"""#977 Phase A: missing/failed/pending/stale evidence must never look like PASS.

担当: ♦️ソラ
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import pr_review_evidence as ev  # noqa: E402

HEAD = "a" * 40
OLD = "b" * 40
BASE = "c" * 40


def run(run_id, name, *, status="completed", conclusion="success", sha=HEAD, attempt=1,
        started="2026-11-28T12:00:00Z"):
    return {"id": run_id, "name": name, "status": status, "conclusion": conclusion,
            "head_sha": sha, "run_attempt": attempt, "event": "pull_request",
            "run_started_at": started}


def review(login, state, *, commit=HEAD, body="担当: ❤️レイ CHANGES_REQUIRED secret"):
    return {"user": {"login": login}, "state": state, "commit_id": commit,
            "submitted_at": "2026-11-28T12:00:00Z", "body": body}


def snapshot(**overrides):
    base = {
        "repository": "sadouninc/Sado-Investment-Lab",
        "event_name": "pull_request",
        "event_action": "synchronize",
        "event_head_sha": HEAD,
        "run_id": 999,
        "run_attempt": 1,
        "collected_at": "2026-11-28T12:00:00+00:00",
        "pull_request": {"number": 977, "head_sha": HEAD, "base_sha": BASE, "draft": True},
        "workflow_runs": [run(1, "PR Preflight"), run(2, "Publish Site")],
        "reviews": [review("sadouninc", "COMMENTED")],
        "review_threads": [{"isResolved": True}],
        "errors": [],
    }
    base.update(overrides)
    return base


class OverallStatusTests(unittest.TestCase):
    def test_best_case_is_evidence_collected_never_pass_or_approval(self):
        report = ev.build_report(snapshot())
        self.assertEqual(report["status"], "EVIDENCE_COLLECTED")
        self.assertFalse(report["is_approval"])
        self.assertNotIn("PASS", json.dumps(report))
        self.assertFalse(report["coverage"]["independent_review_verified"])
        self.assertFalse(report["coverage"]["ux_verified"])

    def test_stale_event_head_is_stale_even_when_everything_else_is_green(self):
        report = ev.build_report(snapshot(event_head_sha=OLD))
        self.assertEqual(report["status"], "STALE")
        self.assertEqual(report["head"]["status"], "STALE")
        # Nothing is evaluated against an exact head that is not current.
        self.assertEqual(report["ci"]["status"], "UNKNOWN")

    def test_pending_ci_is_pending(self):
        runs = [run(1, "PR Preflight"), run(2, "Publish Site", status="in_progress", conclusion=None)]
        self.assertEqual(ev.build_report(snapshot(workflow_runs=runs))["status"], "PENDING")

    def test_failed_ci_blocks(self):
        runs = [run(1, "PR Preflight", conclusion="failure"), run(2, "Publish Site")]
        report = ev.build_report(snapshot(workflow_runs=runs))
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("CI failed on exact head", report["reasons"])

    def test_missing_inputs_are_unknown(self):
        for key in ("workflow_runs", "reviews", "review_threads"):
            report = ev.build_report(snapshot(**{key: None}))
            self.assertEqual(report["status"], "UNKNOWN", key)

    def test_empty_inventories_are_not_pass(self):
        self.assertEqual(ev.build_report(snapshot(workflow_runs=[]))["status"], "UNKNOWN")
        self.assertEqual(ev.build_report(snapshot(reviews=[]))["status"], "UNKNOWN")

    def test_unresolved_thread_blocks(self):
        report = ev.build_report(snapshot(review_threads=[{"isResolved": False}, {"isResolved": True}]))
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["review_threads"]["unresolved"], 1)

    def test_totally_broken_snapshot_is_unknown_not_exception(self):
        for broken in (None, [], "x", {}, {"pull_request": "x"}, {"errors": "boom"}):
            report = ev.build_report(broken)
            self.assertEqual(report["status"], "UNKNOWN", broken)


class CiClassificationTests(unittest.TestCase):
    def test_own_workflow_never_vouches_for_itself(self):
        runs = [run(999, "anything"), run(5, ev.SELF_WORKFLOW_NAME, status="in_progress", conclusion=None)]
        ci = ev.classify_ci(runs, head_sha=HEAD, self_run_id=999)
        self.assertEqual(ci["status"], "UNKNOWN")
        self.assertEqual(ci["observed"], [])

    def test_runs_for_another_commit_are_ignored(self):
        ci = ev.classify_ci([run(1, "PR Preflight", sha=OLD)], head_sha=HEAD, self_run_id=None)
        self.assertEqual(ci["status"], "UNKNOWN")

    def test_latest_attempt_per_workflow_wins(self):
        runs = [run(1, "PR Preflight", conclusion="failure", attempt=1),
                run(1, "PR Preflight", conclusion="success", attempt=2)]
        self.assertEqual(ev.classify_ci(runs, head_sha=HEAD, self_run_id=None)["status"], "SUCCESS")
        rerun_failed = [run(1, "PR Preflight", attempt=1), run(1, "PR Preflight", conclusion="failure", attempt=2)]
        self.assertEqual(ev.classify_ci(rerun_failed, head_sha=HEAD, self_run_id=None)["status"], "FAILED")

    def test_distinct_runs_are_ordered_by_latest_attempt_start_not_attempt_number(self):
        # Re-run (attempt 2) of older run 5 started after newer run 10: the re-run wins.
        rerun_later = [run(5, "PR Preflight", conclusion="failure", attempt=2, started="2026-11-28T12:30:00Z"),
                       run(10, "PR Preflight", conclusion="success", attempt=1, started="2026-11-28T12:10:00Z")]
        ci = ev.classify_ci(rerun_later, head_sha=HEAD, self_run_id=None)
        self.assertEqual(ci["status"], "FAILED")
        self.assertEqual(ci["observed"][0]["id"], 5)
        # Newer run 10 started after the old run's re-run: run 10 wins despite attempt=1.
        newer_run_later = [run(5, "PR Preflight", conclusion="failure", attempt=2, started="2026-11-28T12:10:00Z"),
                           run(10, "PR Preflight", conclusion="success", attempt=1, started="2026-11-28T12:30:00Z")]
        ci = ev.classify_ci(newer_run_later, head_sha=HEAD, self_run_id=None)
        self.assertEqual(ci["status"], "SUCCESS")
        self.assertEqual(ci["observed"][0]["id"], 10)
        self.assertNotIn("_order", ci["observed"][0])

    def test_missing_or_malformed_start_time_falls_back_to_run_id(self):
        runs = [run(5, "PR Preflight", conclusion="failure", attempt=3, started=None),
                run(10, "PR Preflight", conclusion="success", attempt=1, started="garbage")]
        self.assertEqual(ev.classify_ci(runs, head_sha=HEAD, self_run_id=None)["observed"][0]["id"], 10)

    def test_cancelled_or_timed_out_is_failure_and_unknown_conclusion_is_unknown(self):
        for conclusion in ("cancelled", "timed_out", "action_required", "startup_failure", "stale"):
            ci = ev.classify_ci([run(1, "X", conclusion=conclusion)], head_sha=HEAD, self_run_id=None)
            self.assertEqual(ci["status"], "FAILED", conclusion)
        ci = ev.classify_ci([run(1, "X", conclusion="weird")], head_sha=HEAD, self_run_id=None)
        self.assertEqual(ci["status"], "UNKNOWN")

    def test_malformed_run_records_make_ci_unknown(self):
        for bad in ([None], [{"id": True, "name": "X"}], [{"id": 1}], "runs"):
            self.assertEqual(ev.classify_ci(bad, head_sha=HEAD, self_run_id=None)["status"], "UNKNOWN", bad)


class ReviewClassificationTests(unittest.TestCase):
    def test_commented_is_not_approved(self):
        reviews = ev.classify_reviews([review("sadouninc", "COMMENTED")], head_sha=HEAD)
        self.assertEqual(reviews["approved_on_exact_head"], [])
        self.assertEqual(reviews["commented_on_exact_head"], 1)
        self.assertIn("not equivalent to APPROVED", reviews["note"])

    def test_outstanding_changes_requested_blocks_until_superseded(self):
        blocked = ev.build_report(snapshot(reviews=[review("rei", "CHANGES_REQUESTED", commit=OLD),
                                                    review("mina", "COMMENTED")]))
        self.assertEqual(blocked["status"], "BLOCKED")
        cleared = ev.build_report(snapshot(reviews=[review("rei", "CHANGES_REQUESTED", commit=OLD),
                                                    review("rei", "APPROVED")]))
        self.assertEqual(cleared["status"], "EVIDENCE_COLLECTED")
        self.assertEqual(cleared["reviews"]["approved_on_exact_head"], ["rei"])

    def test_review_only_on_old_head_is_not_exact_head_evidence(self):
        report = ev.build_report(snapshot(reviews=[review("rei", "APPROVED", commit=OLD)]))
        self.assertEqual(report["reviews"]["status"], "NO_EXACT_HEAD_REVIEW")
        self.assertEqual(report["reviews"]["approved_on_exact_head"], [])
        self.assertEqual(report["status"], "UNKNOWN")

    def test_pending_draft_reviews_are_ignored_and_malformed_reviews_are_unknown(self):
        reviews = ev.classify_reviews([review("rei", "PENDING")], head_sha=HEAD)
        self.assertEqual(reviews["status"], "NO_EXACT_HEAD_REVIEW")
        for bad in ([review("rei", "LGTM")], [{"state": "APPROVED"}], [None],
                    [review("bad login!", "APPROVED")]):
            self.assertEqual(ev.classify_reviews(bad, head_sha=HEAD)["status"], "UNKNOWN", bad)

    def test_review_bodies_are_never_stored(self):
        report = ev.build_report(snapshot())
        dumped = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("secret", dumped)
        self.assertNotIn("CHANGES_REQUIRED", dumped)
        self.assertFalse(report["coverage"]["review_bodies_stored"])


class ThreadClassificationTests(unittest.TestCase):
    def test_malformed_threads_are_unknown(self):
        for bad in (None, "x", [{"isResolved": "no"}], [None]):
            self.assertEqual(ev.classify_threads(bad)["status"], "UNKNOWN", bad)
        self.assertEqual(ev.classify_threads([])["status"], "NONE_UNRESOLVED")


class OutputSafetyTests(unittest.TestCase):
    def test_untrusted_text_is_sanitised_and_bounded(self):
        runs = [run(1, "PR Preflight<script>`$(rm -rf /)`" + "x" * 300)]
        report = ev.build_report(snapshot(workflow_runs=runs))
        name = report["ci"]["observed"][0]["name"]
        self.assertNotIn("<", name)
        self.assertNotIn("`", name)
        self.assertNotIn("$", name)
        self.assertLessEqual(len(name), 120)

    def test_japanese_summary_states_it_is_not_approval(self):
        summary = ev.render_summary_ja(ev.build_report(snapshot()))
        self.assertIn("承認ではありません", summary)
        self.assertIn("COMMENTEDは承認ではありません", summary)
        self.assertIn("対象外", summary)
        stale = ev.render_summary_ja(ev.build_report(snapshot(event_head_sha=OLD)))
        self.assertIn("イベント時のHEADが古い", stale)


class JapaneseSummaryUxTests(unittest.TestCase):
    """⭐️ミナ review 6097961675 follow-ups."""

    def test_unknown_review_inventory_shows_unconfirmed_not_zero(self):
        summary = ev.render_summary_ja(ev.build_report(snapshot(reviews=None)))
        self.assertIn("APPROVED: 未確認", summary)
        self.assertIn("COMMENTED: 未確認", summary)
        self.assertIn("古いHEADへのレビュー: 未確認", summary)
        self.assertNotIn("APPROVED: 0件", summary)
        known = ev.render_summary_ja(ev.build_report(snapshot()))
        self.assertIn("APPROVED: 0件", known)
        self.assertIn("COMMENTED: 1件", known)

    def test_statuses_and_reasons_have_japanese_labels(self):
        summary = ev.render_summary_ja(ev.build_report(snapshot(
            workflow_runs=[run(1, "PR Preflight", conclusion="failure")],
            review_threads=[{"isResolved": False}, {"isResolved": False}],
        )))
        self.assertIn("失敗（FAILED）", summary)
        self.assertIn("最新HEADでCIが失敗している（CI failed on exact head）", summary)
        self.assertIn("未解決のレビュースレッドが2件ある", summary)
        unknown_threads = ev.render_summary_ja(ev.build_report(snapshot(review_threads=None)))
        self.assertIn("未解決のレビュースレッド: 未確認（UNKNOWN）", unknown_threads)

    def test_next_action_is_shown_for_every_status(self):
        cases = {
            "EVIDENCE_COLLECTED": snapshot(),
            "PENDING": snapshot(workflow_runs=[run(1, "X", status="in_progress", conclusion=None)]),
            "BLOCKED": snapshot(review_threads=[{"isResolved": False}]),
            "STALE": snapshot(event_head_sha=OLD),
            "UNKNOWN": snapshot(workflow_runs=None),
        }
        for status, snap in cases.items():
            report = ev.build_report(snap)
            self.assertEqual(report["status"], status)
            summary = ev.render_summary_ja(report)
            self.assertIn("次に確認すること:", summary)
            self.assertIn(ev.NEXT_ACTION_JA[status], summary)


class ReadOnlyClientTests(unittest.TestCase):
    def test_only_fixed_read_endpoints_are_allowed(self):
        client = ev.ReadOnlyClient("sadouninc/Sado-Investment-Lab", "token")
        for bad in ("issues/1/comments", "pulls/1/merge", "actions/workflows/x/dispatches",
                    "pulls/0", "../x", "https://evil.example/"):
            with self.assertRaises(ValueError, msg=bad):
                client.get(bad)

    def test_graphql_query_is_a_fixed_read_only_query(self):
        self.assertTrue(ev.THREADS_QUERY.startswith("query("))
        self.assertNotIn("mutation", ev.THREADS_QUERY)

    def test_missing_token_or_bad_repository_fail_closed(self):
        with self.assertRaises(ev.EvidenceUnavailable):
            ev.ReadOnlyClient("sadouninc/Sado-Investment-Lab", "")
        with self.assertRaises(ValueError):
            ev.ReadOnlyClient("not a repo", "token")

    def test_collect_snapshot_records_errors_and_stays_unknown(self):
        client = ev.ReadOnlyClient("sadouninc/Sado-Investment-Lab", "token")
        event = {"action": "opened", "pull_request": {"number": 977, "head": {"sha": HEAD}}}
        with mock.patch.object(client, "_request", side_effect=ev.EvidenceUnavailable("read failed (HTTPError)")):
            snap = ev.collect_snapshot(event, client, run_id=1, run_attempt=1, event_name="pull_request")
        report = ev.build_report(snap)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(report["collection_errors"]), 4)

    def test_collect_snapshot_happy_path_with_fake_api(self):
        client = ev.ReadOnlyClient("sadouninc/Sado-Investment-Lab", "token")
        event = {"action": "synchronize", "pull_request": {"number": 977, "head": {"sha": HEAD}}}

        def fake(url, *, data=None):
            if data is not None:
                return {"data": {"repository": {"pullRequest": {"reviewThreads": {
                    "totalCount": 1, "nodes": [{"isResolved": True}]}}}}}
            if "/actions/runs" in url:
                return {"total_count": 1, "workflow_runs": [run(1, "PR Preflight")]}
            if url.endswith("/reviews?per_page=100"):
                return [review("sadouninc", "COMMENTED")]
            return {"head": {"sha": HEAD}, "base": {"sha": BASE}, "draft": False}

        with mock.patch.object(client, "_request", side_effect=fake):
            snap = ev.collect_snapshot(event, client, run_id=999, run_attempt=1, event_name="pull_request")
        report = ev.build_report(snap)
        self.assertEqual(report["status"], "EVIDENCE_COLLECTED")
        self.assertEqual(report["provenance"]["base_sha"], BASE)
        self.assertEqual(report["provenance"]["run_id"], 999)

    def test_incomplete_inventories_are_not_trusted(self):
        client = ev.ReadOnlyClient("sadouninc/Sado-Investment-Lab", "token")
        event = {"pull_request": {"number": 977, "head": {"sha": HEAD}}}

        def fake(url, *, data=None):
            if data is not None:
                return {"data": {"repository": {"pullRequest": {"reviewThreads": {
                    "totalCount": 150, "nodes": [{"isResolved": True}] * 100}}}}}
            if "/actions/runs" in url:
                return {"total_count": 150, "workflow_runs": [run(1, "PR Preflight")]}
            if "/reviews" in url:
                return [review("sadouninc", "COMMENTED")] * 100
            return {"head": {"sha": HEAD}, "base": {"sha": BASE}}

        with mock.patch.object(client, "_request", side_effect=fake):
            snap = ev.collect_snapshot(event, client, run_id=1, run_attempt=1, event_name="pull_request")
        self.assertIsNone(snap["workflow_runs"])
        self.assertIsNone(snap["reviews"])
        self.assertIsNone(snap["review_threads"])
        self.assertEqual(ev.build_report(snap)["status"], "UNKNOWN")


class CliTests(unittest.TestCase):
    def test_offline_snapshot_mode_writes_json_and_japanese_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap.json").write_text(json.dumps(snapshot()), encoding="utf-8")
            rc = ev.main(["--snapshot", str(root / "snap.json"),
                          "--output", str(root / "out.json"), "--summary", str(root / "out.md")])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads((root / "out.json").read_text())["status"], "EVIDENCE_COLLECTED")
            self.assertIn("PRレビュー証跡", (root / "out.md").read_text(encoding="utf-8"))

    def test_unreadable_snapshot_still_writes_unknown_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snap.json").write_text("{not json", encoding="utf-8")
            rc = ev.main(["--snapshot", str(root / "snap.json"),
                          "--output", str(root / "out.json"), "--summary", str(root / "out.md")])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads((root / "out.json").read_text())["status"], "UNKNOWN")

    def test_non_ascii_digits_in_run_env_are_ignored(self):
        with mock.patch.dict("os.environ", {"GITHUB_RUN_ID": "\u00b2", "GITHUB_RUN_ATTEMPT": "\u0663"}):
            self.assertIsNone(ev._int_env("GITHUB_RUN_ID"))
            self.assertIsNone(ev._int_env("GITHUB_RUN_ATTEMPT"))
        with mock.patch.dict("os.environ", {"GITHUB_RUN_ID": "46147386877"}):
            self.assertEqual(ev._int_env("GITHUB_RUN_ID"), 46147386877)

    def test_live_mode_without_token_writes_unknown_report(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            "os.environ", {"GITHUB_REPOSITORY": "sadouninc/Sado-Investment-Lab", "GH_TOKEN": "",
                           "GITHUB_TOKEN": "", "GITHUB_EVENT_PATH": ""}, clear=False):
            root = Path(tmp)
            ev.main(["--output", str(root / "out.json"), "--summary", str(root / "out.md")])
            self.assertEqual(json.loads((root / "out.json").read_text())["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
