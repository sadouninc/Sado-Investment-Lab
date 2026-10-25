"""Contract tests for the provisional progress dashboard calculation rules."""
import unittest

from progress_metrics import STEPS, closed_loop, compare_snapshots, latest_head_ci, summarize, validate_snapshot


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

    def test_provisional_pass_not_counted_as_verified_delta(self):
        previous = {"scope_version": "v1", "criteria": [
            criterion("a", "UNKNOWN", finalized=False),
        ]}
        current = {"scope_version": "v1", "criteria": [
            criterion("a", "PASS", "https://example.org/unreviewed", finalized=False),
        ]}
        self.assertEqual(compare_snapshots(previous, current)["newly_passed"], [])
        approved = {"scope_version": "v1", "criteria": [
            criterion("a", "PASS", "https://example.org/approved", finalized=True),
        ]}
        self.assertEqual(compare_snapshots(current, approved)["newly_passed"], ["a"])
        self.assertEqual(compare_snapshots(approved, current)["regressed"], ["a"])

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


    def test_latest_head_ci_requires_matching_sha_and_run(self):
        self.assertEqual(latest_head_ci(None, "new", "success", 10)["status"], "UNKNOWN")
        self.assertEqual(latest_head_ci("new", "new", "success", None)["status"], "UNKNOWN")
        self.assertEqual(latest_head_ci("old", "new", "success", 10),
                         {"status": "UNKNOWN", "reason": "STALE_HEAD"})
        self.assertEqual(latest_head_ci("new", "new", "success", 10)["status"], "PASS")

    def test_latest_head_ci_failure_and_pending_are_not_pass(self):
        self.assertEqual(latest_head_ci("new", "new", "failure", 10)["status"], "FAIL")
        self.assertEqual(latest_head_ci("new", "new", "cancelled", 10)["status"], "FAIL")
        self.assertEqual(latest_head_ci("new", "new", None, 10)["status"], "UNKNOWN")
        self.assertEqual(latest_head_ci("new", "new", "queued", 10)["status"], "UNKNOWN")


    def test_snapshot_schema_accepts_provisional_unknown(self):
        snapshot = {"scope_version": "PROVISIONAL-867-v1", "criteria": [
            criterion("PV867-T01-C01", "UNKNOWN", None, finalized=False)]}
        self.assertIs(validate_snapshot(snapshot), snapshot)
        self.assertEqual(summarize(snapshot["criteria"], "implementation")["status"], "UNKNOWN")

    def test_snapshot_schema_rejects_bad_ids_and_evidence(self):
        valid = criterion("a", "PASS", "https://example.org/run/1")
        for items in ([valid, valid], [criterion("")],
                      [criterion("a", "PASS", "http://example.org/unsafe")],
                      [criterion("a", "PASS", "not-a-url")],
                      [dict(valid, finalized="yes")],
                      [dict(valid, dimension="other")]):
            with self.subTest(items=items):
                with self.assertRaises(ValueError):
                    validate_snapshot({"scope_version": "v1", "criteria": items})

    def test_snapshot_schema_requires_scope_and_list(self):
        for snapshot in ({}, {"scope_version": "", "criteria": []},
                         {"scope_version": "v1", "criteria": None}):
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(ValueError):
                    validate_snapshot(snapshot)


    def test_snapshot_delta_rejects_malformed_previous_and_current(self):
        valid = {"scope_version": "v1", "criteria": [criterion("a")]}
        invalid_snapshots = [
            {"scope_version": "v1", "criteria": [criterion("a"), criterion("a")]},
            {"scope_version": "v1", "criteria": [dict(criterion("a"), state="DONE")]},
            {"scope_version": "v1", "criteria": "not a list"},
            {"scope_version": "", "criteria": [criterion("a")]},
        ]
        for invalid in invalid_snapshots:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    compare_snapshots(invalid, valid)
                with self.assertRaises(ValueError):
                    compare_snapshots(valid, invalid)



    def test_closed_loop_rejects_empty_or_malformed_linkage(self):
        base = [{"step": name, "work_ref": "work-a", "lease_id": "lease-1",
                 "state": "PASS", "evidence_url": "https://example.org/evidence"}
                for name in STEPS]
        for field, value in (("work_ref", ""), ("lease_id", "  "),
                             ("work_ref", None), ("lease_id", [])):
            steps = [dict(item) for item in base]
            steps[0][field] = value
            with self.subTest(field=field, value=value):
                self.assertEqual(closed_loop(steps)["complete"], 0)
        self.assertEqual(closed_loop(None)["complete"], 0)
        self.assertEqual(closed_loop([None] * 9)["complete"], 0)

    def test_closed_loop_rejects_invalid_evidence_url(self):
        base = [{"step": name, "work_ref": "work-a", "lease_id": "lease-1",
                 "state": "PASS", "evidence_url": "https://example.org/evidence"}
                for name in STEPS]
        for value in ("", "http://example.org/no", "not-a-link", [], None):
            steps = [dict(item) for item in base]
            steps[-1]["evidence_url"] = value
            with self.subTest(value=value):
                result = closed_loop(steps)
                self.assertEqual(result["passed"], 8)
                self.assertEqual(result["complete"], 0)


if __name__ == "__main__":
    unittest.main()
