"""#1000: review wait / revision turnaround intervals from synthetic timelines.

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

from scripts import review_turnaround_metrics as rt  # noqa: E402

H1, H2, H3 = "a" * 40, "b" * 40, "c" * 40


def ev(type_, at, **kw):
    return {"type": type_, "at": at, **kw}


def full_cycle():
    return [
        ev("opened", "2026-11-28T10:00:00Z", head_sha=H1, draft=True),
        ev("ready_for_review", "2026-11-28T10:30:00Z"),
        ev("review", "2026-11-28T11:00:00Z", state="COMMENTED", commit_id=H1, verdict="CHANGES_REQUIRED"),
        ev("push", "2026-11-28T11:20:00Z", head_sha=H2),
        ev("review", "2026-11-28T11:50:00Z", state="COMMENTED", commit_id=H2),
        ev("merged", "2026-11-28T12:10:00Z", head_sha=H2),
    ]


def by_name(result, name):
    return [i for i in result["intervals"] if i["interval"] == name]


class IntervalTests(unittest.TestCase):
    def test_full_cycle_intervals(self):
        result = rt.compute_turnaround(full_cycle())
        self.assertEqual(by_name(result, "ready_to_review")[0]["seconds"], 1800)
        self.assertEqual(by_name(result, "changes_to_revision")[0]["seconds"], 1200)
        self.assertEqual(by_name(result, "revision_to_rereview")[0]["seconds"], 1800)
        self.assertEqual(by_name(result, "merge_wait")[0]["seconds"], 1200)
        self.assertTrue(all(i["status"] == "OK" for i in result["intervals"]))
        self.assertEqual(result["summary"]["ready_to_review"]["median_seconds"], 1800)

    def test_non_draft_open_counts_as_ready(self):
        timeline = [ev("opened", "2026-11-28T10:00:00Z", head_sha=H1),
                    ev("review", "2026-11-28T10:10:00Z", state="APPROVED", commit_id=H1)]
        self.assertEqual(by_name(rt.compute_turnaround(timeline), "ready_to_review")[0]["seconds"], 600)

    def test_github_changes_requested_state_also_counts(self):
        timeline = full_cycle()
        timeline[2] = ev("review", "2026-11-28T11:00:00Z", state="CHANGES_REQUESTED", commit_id=H1)
        self.assertEqual(by_name(rt.compute_turnaround(timeline), "changes_to_revision")[0]["status"], "OK")

    def test_multiple_revision_cycles(self):
        timeline = full_cycle()[:-1] + [
            ev("review", "2026-11-28T12:00:00Z", state="COMMENTED", commit_id=H2, verdict="CHANGES_REQUIRED"),
            ev("push", "2026-11-28T12:30:00Z", head_sha=H3),
            ev("review", "2026-11-28T12:40:00Z", state="COMMENTED", commit_id=H3),
            ev("merged", "2026-11-28T13:00:00Z", head_sha=H3),
        ]
        result = rt.compute_turnaround(timeline)
        self.assertEqual([i["seconds"] for i in by_name(result, "changes_to_revision")], [1200, 1800])
        self.assertEqual(result["summary"]["revision_to_rereview"]["total_seconds"], 1800 + 600)


class FailClosedTests(unittest.TestCase):
    def test_missing_events_are_unknown_not_zero(self):
        timeline = full_cycle()[:3]  # change requested, never revised
        result = rt.compute_turnaround(timeline)
        entry = by_name(result, "changes_to_revision")[0]
        self.assertEqual((entry["status"], entry["seconds"]), ("UNKNOWN", None))
        self.assertEqual(by_name(result, "merge_wait"), [])

    def test_review_on_wrong_head_is_unknown(self):
        timeline = full_cycle()
        timeline[4] = ev("review", "2026-11-28T11:50:00Z", state="COMMENTED", commit_id=H1)  # stale head
        result = rt.compute_turnaround(timeline)
        entry = by_name(result, "revision_to_rereview")[0]
        self.assertEqual(entry["status"], "UNKNOWN")
        self.assertIn("different head", entry["reason"])
        self.assertEqual(by_name(result, "merge_wait")[0]["status"], "UNKNOWN")

    def test_change_request_on_unobserved_head_is_unknown(self):
        timeline = [ev("ready_for_review", "2026-11-28T10:00:00Z"),
                    ev("review", "2026-11-28T10:10:00Z", state="CHANGES_REQUESTED", commit_id=H1)]
        result = rt.compute_turnaround(timeline)
        self.assertEqual(by_name(result, "ready_to_review")[0]["status"], "UNKNOWN")
        self.assertEqual(by_name(result, "changes_to_revision")[0]["status"], "UNKNOWN")

    def test_malformed_timestamps_and_fields_are_counted_and_dropped(self):
        timeline = full_cycle() + [
            ev("review", "2026-02-30T00:00:00Z", state="APPROVED", commit_id=H2),
            ev("review", "2026-11-28T12:00:00+09:00", state="APPROVED", commit_id=H2),
            ev("review", "2026-11-28T12:00:00Z", state="LGTM", commit_id=H2),
            ev("push", "2026-11-28T12:00:00Z", head_sha="zz"),
            ev("deploy", "2026-11-28T12:00:00Z"), None,
        ]
        result = rt.compute_turnaround(timeline)
        self.assertEqual(result["event_counts"]["malformed"], 6)
        self.assertTrue(all(i["status"] == "OK" for i in result["intervals"]))

    def test_identical_events_are_deduplicated(self):
        timeline = full_cycle()
        timeline.insert(3, copy.deepcopy(timeline[2]))
        result = rt.compute_turnaround(timeline)
        self.assertEqual(result["event_counts"]["duplicates"], 1)
        self.assertEqual(len(by_name(result, "changes_to_revision")), 1)

    def test_merge_without_review_on_merged_head_is_unknown(self):
        timeline = full_cycle()[:4] + [ev("merged", "2026-11-28T11:30:00Z", head_sha=H2)]
        entry = by_name(rt.compute_turnaround(timeline), "merge_wait")[0]
        self.assertEqual(entry["status"], "UNKNOWN")

    def test_non_list_input_is_safe(self):
        for bad in (None, "x", {"events": []}):
            result = rt.compute_turnaround(bad)
            self.assertEqual(result["intervals"], [])
            self.assertEqual(result["event_counts"]["malformed"], 1)

    def test_output_json_and_input_not_mutated(self):
        timeline = full_cycle()
        snapshot = copy.deepcopy(timeline)
        json.dumps(rt.compute_turnaround(timeline))
        self.assertEqual(timeline, snapshot)


if __name__ == "__main__":
    unittest.main()
