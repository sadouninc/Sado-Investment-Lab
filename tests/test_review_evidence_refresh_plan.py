"""#999: refresh plan after CI / review events (pure, no side effects).

担当: ♦️ソラ
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import review_evidence_refresh_plan as rp  # noqa: E402

H1 = "a" * 40
H2 = "b" * 40


def pr(action, head=H1, at="2026-11-28T12:00:00Z", merged=False):
    return {"kind": "pull_request", "action": action, "head_sha": head, "at": at, "merged": merged}


def run(name, run_id, *, head=H1, at="2026-11-28T12:05:00Z", status="completed", conclusion="success", attempt=1):
    return {"kind": "workflow_run", "name": name, "run_id": run_id, "run_attempt": attempt,
            "head_sha": head, "at": at, "status": status, "conclusion": conclusion}


def review(at="2026-11-28T12:10:00Z", head=H1):
    return {"kind": "review", "head_sha": head, "at": at, "action": "submitted"}


def prev(head=H1, at="2026-11-28T12:01:00Z", status="PENDING", key=None, count=1):
    return {"head_sha": head, "collected_at": at, "status": status, "refresh_key": key, "refresh_count": count}


class DecisionTests(unittest.TestCase):
    def test_first_evidence_for_head_is_refresh(self):
        plan = rp.plan_refresh([pr("opened")])
        self.assertEqual(plan["decision"], "REFRESH")
        self.assertEqual(plan["latest_head"], H1)
        self.assertIn("side_effects", plan)

    def test_ci_completion_after_pending_evidence_triggers_refresh(self):
        events = [pr("opened"), run("PR Preflight", 1, status="in_progress", conclusion=None, at="2026-11-28T12:00:30Z"),
                  run("PR Preflight", 1, at="2026-11-28T12:05:00Z")]
        plan = rp.plan_refresh(events, prev())
        self.assertEqual(plan["decision"], "REFRESH")
        self.assertEqual(plan["latest_runs"][0]["status"], "completed")

    def test_still_running_ci_waits(self):
        events = [pr("opened"), run("PR Preflight", 1, status="in_progress", conclusion=None, at="2026-11-28T12:02:00Z")]
        plan = rp.plan_refresh(events, prev())
        self.assertEqual(plan["decision"], "WAIT")
        self.assertIn("still in progress", plan["reasons"][-1])

    def test_review_event_triggers_refresh_even_while_ci_runs(self):
        events = [pr("opened"), run("PR Preflight", 1, status="in_progress", conclusion=None), review()]
        self.assertEqual(rp.plan_refresh(events, prev())["decision"], "REFRESH")

    def test_nothing_new_waits(self):
        plan = rp.plan_refresh([pr("opened")], prev(status="EVIDENCE_COLLECTED"))
        self.assertEqual(plan["decision"], "WAIT")

    def test_new_head_refreshes_and_old_head_events_are_ignored(self):
        events = [pr("opened"), pr("synchronize", head=H2, at="2026-11-28T12:20:00Z"),
                  run("PR Preflight", 9, head=H1, at="2026-11-28T12:30:00Z")]
        plan = rp.plan_refresh(events, prev())
        self.assertEqual(plan["decision"], "REFRESH")
        self.assertEqual(plan["latest_head"], H2)
        self.assertEqual(plan["latest_runs"], [])
        self.assertTrue(any("older heads ignored" in r for r in plan["reasons"]))


class TerminationAndDedupTests(unittest.TestCase):
    def test_closed_or_merged_is_terminal_done(self):
        plan = rp.plan_refresh([pr("opened"), pr("closed", at="2026-11-28T13:00:00Z", merged=True)], prev())
        self.assertEqual((plan["decision"], plan["terminal"]), ("DONE", True))
        self.assertIn("merged", plan["reasons"][-1])

    def test_reopen_after_close_resumes(self):
        events = [pr("opened"), pr("closed", at="2026-11-28T13:00:00Z"), pr("reopened", at="2026-11-28T13:05:00Z")]
        self.assertEqual(rp.plan_refresh(events)["decision"], "REFRESH")

    def test_refresh_bound_is_terminal(self):
        events = [pr("opened"), review()]
        plan = rp.plan_refresh(events, prev(count=6), max_refreshes_per_head=6)
        self.assertEqual((plan["decision"], plan["terminal"]), ("DONE", True))

    def test_same_trigger_is_not_refreshed_twice(self):
        events = [pr("opened"), review()]
        first = rp.plan_refresh(events, prev())
        self.assertEqual(first["decision"], "REFRESH")
        again = rp.plan_refresh(events, prev(at="2026-11-28T12:11:00Z", key=first["refresh_key"], count=2))
        self.assertEqual(again["decision"], "WAIT")
        self.assertIn("duplicate suppressed", again["reasons"][-1])

    def test_identical_events_are_deduplicated(self):
        events = [pr("opened"), review(), review()]
        plan = rp.plan_refresh(events, prev())
        self.assertEqual(plan["event_counts"]["duplicates"], 1)


class MalformedInputTests(unittest.TestCase):
    def test_unknown_head_is_unknown(self):
        self.assertEqual(rp.plan_refresh([])["decision"], "UNKNOWN")
        self.assertEqual(rp.plan_refresh("events")["decision"], "UNKNOWN")
        self.assertEqual(rp.plan_refresh([review()])["decision"], "UNKNOWN")  # no head event, no previous

    def test_malformed_events_are_counted_and_ignored(self):
        bad = [None, {"kind": "push"}, {"kind": "review", "head_sha": "zz", "at": "2026-11-28T12:00:00Z"},
               {"kind": "review", "head_sha": H1, "at": "2026-02-30T00:00:00Z"},
               {"kind": "workflow_run", "head_sha": H1, "at": "2026-11-28T12:00:00Z", "run_id": True, "name": "x"}]
        plan = rp.plan_refresh([pr("opened"), *bad], prev(status="EVIDENCE_COLLECTED"))
        self.assertEqual(plan["event_counts"]["malformed"], 5)
        self.assertEqual(plan["decision"], "WAIT")

    def test_malformed_previous_record_refreshes(self):
        for broken in (prev(at="yesterday"), prev(status="PASS"), prev(count=-1), prev(count=True)):
            self.assertEqual(rp.plan_refresh([pr("opened")], broken)["decision"], "REFRESH", broken)

    def test_previous_head_used_when_no_head_event_observed(self):
        plan = rp.plan_refresh([review()], prev())
        self.assertEqual((plan["decision"], plan["latest_head"]), ("REFRESH", H1))


class RunSelectionTests(unittest.TestCase):
    def test_latest_run_by_time_not_attempt_number(self):
        events = [pr("opened"),
                  run("PR Preflight", 5, attempt=2, at="2026-11-28T12:30:00Z", conclusion="failure"),
                  run("PR Preflight", 10, attempt=1, at="2026-11-28T12:10:00Z")]
        runs = rp.plan_refresh(events)["latest_runs"]
        self.assertEqual((runs[0]["run_id"], runs[0]["run_attempt"]), (5, 2))

    def test_output_is_json_and_input_not_mutated(self):
        events = [pr("opened"), review()]
        snapshot = copy.deepcopy(events)
        json.dumps(rp.plan_refresh(events, prev()))
        self.assertEqual(events, snapshot)


if __name__ == "__main__":
    unittest.main()
