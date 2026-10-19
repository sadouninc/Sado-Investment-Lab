"""Contract tests for the provisional progress dashboard calculation rules."""
import unittest

from progress_metrics import STEPS, closed_loop, compare_snapshots, summarize


def criterion(cid, state="UNKNOWN", evidence=None, dimension="implementation", finalized=True):
    return {"criterion_id": cid, "state": state, "evidence_url": evidence,
            "dimension": dimension, "finalized": finalized}


class ProgressMetricsTest(unittest.TestCase):
    def test_unknown_and_zero_denominator(self):
        self.assertEqual(summarize([], "implementation")["percent"], None)
        self.assertEqual(summarize([criterion("a", finalized=False)], "implementation")["percent"], None)
        result = summarize([criterion("a")], "implementation")
        self.assertEqual((result["passed"], result["total"], result["percent"]), (0, 1, 0))

    def test_pass_requires_evidence_and_dimensions_separate(self):
        items = [criterion("a", "PASS"), criterion("b", "PASS", "https://example.org/commit"),
                 criterion("c", "PASS", "https://example.org/ci", "verification"),
                 criterion("d", "UNKNOWN", None, "production")]
        self.assertEqual(summarize(items, "implementation")["passed"], 1)
        self.assertEqual(summarize(items, "verification")["passed"], 1)
        self.assertEqual(summarize(items, "production")["passed"], 0)

    def test_scope_delta_not_progress_delta(self):
        previous = {"scope_version": "v1", "criteria": [criterion("a")]}
        current = {"scope_version": "v1", "criteria": [criterion("a"), criterion("b")]}
        result = compare_snapshots(previous, current)
        self.assertEqual(result["status"], "SCOPE_CHANGED")
        self.assertEqual(result["scope_delta"]["added"], ["b"])
        self.assertIsNone(result["newly_passed"])

    def test_same_scope_transitions(self):
        previous = {"scope_version": "v1", "criteria": [criterion("a"), criterion("b", "BLOCKED"),
                    criterion("c", "PASS", "https://example.org/old")]}
        current = {"scope_version": "v1", "criteria": [criterion("a", "PASS", "https://example.org/new"),
                   criterion("b"), criterion("c", "BLOCKED")]}
        result = compare_snapshots(previous, current)
        self.assertEqual(result["newly_passed"], ["a"])
        self.assertEqual(result["regressed"], ["c"])
        self.assertEqual(result["new_blockers"], ["c"])
        self.assertEqual(result["resolved_blockers"], ["b"])
        self.assertEqual(result["remaining_blockers"], ["c"])

    def test_closed_loop_rejects_mixed_work(self):
        steps = [{"step": name, "work_ref": "work-a", "lease_id": "lease-1",
                  "state": "PASS", "evidence_url": "https://example.org/evidence"}
                 for name in STEPS]
        self.assertEqual(closed_loop(steps)["complete"], 1)
        steps[4]["work_ref"] = "work-b"
        self.assertEqual(closed_loop(steps)["complete"], 0)

    def test_closed_loop_unknown_not_success(self):
        steps = [{"step": name, "work_ref": "work-a", "lease_id": "lease-1",
                  "state": "UNKNOWN", "evidence_url": None} for name in STEPS]
        self.assertEqual(closed_loop(steps), {"passed": 0, "total": 9, "complete": 0})


    def test_regression_when_pass_evidence_disappears(self):
        previous = {"scope_version": "v1", "criteria": [
            criterion("a", "PASS", "https://example.org/run/1")]}
        current = {"scope_version": "v1", "criteria": [
            criterion("a", "PASS", None)]}
        result = compare_snapshots(previous, current)
        self.assertEqual(result["status"], "COMPARABLE")
        self.assertEqual(result["regressed"], ["a"])
        self.assertEqual(result["newly_passed"], [])

    def test_scope_version_change_without_criterion_change(self):
        previous = {"scope_version": "v1", "criteria": [criterion("a")]}
        current = {"scope_version": "v2", "criteria": [criterion("a")]}
        result = compare_snapshots(previous, current)
        self.assertEqual(result["status"], "SCOPE_CHANGED")
        self.assertEqual(result["scope_delta"], {"added": [], "removed": []})
        self.assertIsNone(result["remaining_blockers"])

    def test_duplicate_criterion_ids_and_invalid_state_rejected(self):
        with self.assertRaises(ValueError):
            summarize([criterion("a"), criterion("a")], "implementation")
        with self.assertRaises(ValueError):
            summarize([criterion("a", "DONE")], "implementation")
        with self.assertRaises(ValueError):
            summarize([criterion("a")], "other")

    def test_closed_loop_requires_evidence_for_each_stage(self):
        steps = [{"step": name, "work_ref": "work-a", "lease_id": "lease-1",
                  "state": "PASS", "evidence_url": "https://example.org/evidence"}
                 for name in STEPS]
        steps[5]["evidence_url"] = None
        self.assertEqual(closed_loop(steps), {"passed": 8, "total": 9, "complete": 0})
        steps[5]["evidence_url"] = "https://example.org/ci"
        self.assertEqual(closed_loop(steps), {"passed": 9, "total": 9, "complete": 1})


if __name__ == "__main__":
    unittest.main()
