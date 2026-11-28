"""Synthetic unit tests for #991 offline work-supply capacity classifier."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.work_supply_capacity import classify_work_supply_capacity, main


def _ready_item(
    issue: int,
    *,
    state: str = "READY",
    owner_slice: str | None = None,
    allowed_paths: list[str] | None = None,
    dependencies_satisfied: bool = True,
    stop_clear: bool = True,
    updated_at: str | None = None,
) -> dict:
    item = {
        "issue": issue,
        "state": state,
        "owner_slice": owner_slice if owner_slice is not None else f"slice-{issue}",
        "allowed_paths": allowed_paths if allowed_paths is not None else [f"scripts/mod_{issue}.py"],
        "dependencies_satisfied": dependencies_satisfied,
        "stop_clear": stop_clear,
    }
    if updated_at is not None:
        item["updated_at"] = updated_at
    return item


_UNSET = object()


def _snapshot(
    items: list[dict],
    *,
    complete: bool = True,
    open_prs: Any = _UNSET,
    as_of: str | None = "2026-11-28T12:00:00Z",
) -> dict:
    payload: dict = {
        "complete": complete,
        "items": items,
        "open_prs": {"complete": True, "prs": []} if open_prs is _UNSET else open_prs,
    }
    if as_of is not None:
        payload["as_of"] = as_of
    return payload


class WorkSupplyCapacityTests(unittest.TestCase):
    def test_complete_empty_inventory_reports_zero_starvation(self):
        result = classify_work_supply_capacity(_snapshot([]))
        self.assertTrue(result["complete"])
        self.assertFalse(result["dispatch_allowed"])
        self.assertFalse(result["merge_authorized"])
        self.assertEqual(0, result["prepared_count"])
        self.assertEqual(0, result["verified_ready_count"])
        self.assertEqual("REPLENISH", result["prepared_status"])
        self.assertEqual("STARVATION", result["ready_replenishment_status"])

    def test_incomplete_snapshot_or_open_prs_is_unknown_never_zero(self):
        for bad_snapshot in (
            _snapshot([], complete=False),
            _snapshot([], open_prs={"complete": False, "prs": []}),
            _snapshot([], open_prs=None),
            "not-a-mapping",
            {"complete": True, "items": "not-a-list", "open_prs": {"complete": True, "prs": []}},
        ):
            result = classify_work_supply_capacity(bad_snapshot)
            self.assertFalse(result["complete"])
            self.assertFalse(result["dispatch_allowed"])
            self.assertIsNone(result["prepared_count"])
            self.assertIsNone(result["verified_ready_count"])
            self.assertEqual("UNKNOWN", result["prepared_status"])
            self.assertEqual("UNKNOWN", result["ready_replenishment_status"])
            self.assertIsNone(result["counts"]["verified_ready"])

    def test_duplicate_issues_or_prs_fail_closed_as_unknown(self):
        dup_issues = _snapshot([_ready_item(1001), _ready_item(1001)])
        res_issues = classify_work_supply_capacity(dup_issues)
        self.assertFalse(res_issues["complete"])
        self.assertIsNone(res_issues["verified_ready_count"])
        self.assertEqual("UNKNOWN", res_issues["ready_replenishment_status"])
        self.assertEqual([1001], res_issues["diagnostics"]["duplicate_issues"])

        dup_prs = _snapshot(
            [_ready_item(1002)],
            open_prs={
                "complete": True,
                "prs": [
                    {"number": 500, "paths": ["scripts/a.py"], "wait_state": "REVIEW_WAIT"},
                    {"number": 500, "paths": ["scripts/b.py"], "wait_state": "REVIEW_WAIT"},
                ],
            },
        )
        res_prs = classify_work_supply_capacity(dup_prs)
        self.assertFalse(res_prs["complete"])
        self.assertIsNone(res_prs["verified_ready_count"])
        self.assertEqual([500], res_prs["diagnostics"]["duplicate_prs"])

    def test_issue_79_is_strictly_excluded_from_all_capacity(self):
        snap = _snapshot([_ready_item(79), _ready_item(1010)])
        result = classify_work_supply_capacity(snap)
        self.assertEqual(1, result["prepared_count"])
        self.assertEqual(1, result["verified_ready_count"])
        self.assertEqual([1010], result["issues_by_bucket"]["verified_ready"])
        self.assertEqual(1, result["diagnostics"]["excluded_issue_79_count"])
        self.assertTrue(result["issue_79_excluded"])
        for items in result["issues_by_bucket"].values():
            self.assertNotIn(79, items)

    def test_open_pr_linked_items_are_not_ready_and_distinguish_wait_vs_active(self):
        snap = _snapshot(
            [
                _ready_item(2001, state="READY"),
                _ready_item(2002, state="READY"),
                _ready_item(2003, state="READY"),
            ],
            open_prs={
                "complete": True,
                "prs": [
                    {
                        "number": 901,
                        "paths": ["scripts/mod_2001.py"],
                        "linked_issues": [2001],
                        "wait_state": "REVIEW_WAIT",
                        "updated_at": "2026-11-28T09:00:00Z",
                    },
                    {
                        "number": 902,
                        "paths": ["scripts/mod_2002.py"],
                        "linked_issues": [2002],
                        "wait_state": "REVISION_REQUIRED",
                        "updated_at": "2026-11-28T10:00:00Z",
                    },
                ],
            },
        )
        result = classify_work_supply_capacity(snap)
        self.assertEqual(1, result["prepared_count"])
        self.assertEqual(1, result["verified_ready_count"])
        self.assertEqual([2003], result["issues_by_bucket"]["verified_ready"])
        self.assertEqual([2001], result["issues_by_bucket"]["ci_review_merge_wait"])
        self.assertEqual([2002], result["issues_by_bucket"]["active_implementation"])
        self.assertEqual(1, result["counts"]["ci_review_merge_wait"])
        self.assertEqual(1, result["counts"]["active_implementation"])
        self.assertEqual(3.0, result["age_summary"]["max_ci_review_merge_wait_hours"])

    def test_missing_owner_path_dependency_stop_evidence_remains_unknown(self):
        missing_owner = _ready_item(3001)
        missing_owner["owner_slice"] = ""
        missing_paths = _ready_item(3002)
        missing_paths["allowed_paths"] = []
        missing_dep = _ready_item(3003)
        del missing_dep["dependencies_satisfied"]
        missing_stop = _ready_item(3004)
        missing_stop["stop_clear"] = None

        result = classify_work_supply_capacity(
            _snapshot([missing_owner, missing_paths, missing_dep, missing_stop])
        )
        self.assertEqual(0, result["prepared_count"])
        self.assertEqual(0, result["verified_ready_count"])
        self.assertEqual(4, result["counts"]["unknown"])
        self.assertEqual([3001, 3002, 3003, 3004], result["issues_by_bucket"]["unknown"])

    def test_dependency_and_path_conflicts_block_ready_but_keep_prepared_count(self):
        dep_blocked = _ready_item(4001, dependencies_satisfied=False)
        pr_path_conflict = _ready_item(4002, allowed_paths=["scripts/shared.py"])
        active_impl = _ready_item(4003, state="IMPLEMENTING", owner_slice="sora-active", allowed_paths=["scripts/active.py"])
        active_conflict = _ready_item(4004, allowed_paths=["scripts/active.py"])
        next_item = _ready_item(4005, state="NEXT")

        snap = _snapshot(
            [dep_blocked, pr_path_conflict, active_impl, active_conflict, next_item],
            open_prs={
                "complete": True,
                "prs": [{"number": 950, "paths": ["scripts/shared.py"], "wait_state": "CI_WAIT"}],
            },
        )
        result = classify_work_supply_capacity(snap)
        self.assertEqual(4, result["prepared_count"])
        self.assertEqual(0, result["verified_ready_count"])
        self.assertEqual(1, result["counts"]["prepared_non_ready"])
        self.assertEqual([4001, 4002, 4004], result["issues_by_bucket"]["dependency_path_blocked"])
        self.assertEqual([4003], result["issues_by_bucket"]["active_implementation"])
        self.assertEqual(1, result["counts"]["ci_review_merge_wait"])

    def test_ready_and_prepared_threshold_boundaries(self):
        cases = [
            (0, "STARVATION", "REPLENISH"),
            (1, "URGENT", "REPLENISH"),
            (4, "URGENT", "REPLENISH"),
            (5, "REPLENISH", "BELOW_TARGET"),
            (9, "REPLENISH", "BELOW_TARGET"),
            (10, "ON_TARGET", "ON_TARGET"),
            (20, "ON_TARGET", "ON_TARGET"),
            (21, "ON_TARGET", "ABOVE_TARGET"),
        ]
        for ready_n, expected_ready_status, expected_prepared_status in cases:
            items = [_ready_item(5000 + i) for i in range(ready_n)]
            res = classify_work_supply_capacity(_snapshot(items))
            self.assertEqual(expected_ready_status, res["ready_replenishment_status"], f"ready_n={ready_n}")
            self.assertEqual(expected_prepared_status, res["prepared_status"], f"ready_n={ready_n}")

    def test_no_wall_clock_assumption_and_no_raw_text_leak(self):
        item = _ready_item(6001, state="REVIEW_WAIT", updated_at="2026-11-28T06:00:00Z")
        item["body"] = "SENSITIVE_RAW_ISSUE_BODY_SHOULD_NOT_APPEAR"
        item["secret_token"] = "gho_should_not_appear"
        without_as_of = classify_work_supply_capacity(_snapshot([item], as_of=None))
        self.assertFalse(without_as_of["age_summary"]["as_of_valid"])
        self.assertIsNone(without_as_of["item_classifications"][0]["age_hours"])
        serialized = json.dumps(without_as_of)
        self.assertNotIn("SENSITIVE_RAW_ISSUE_BODY_SHOULD_NOT_APPEAR", serialized)
        self.assertNotIn("gho_should_not_appear", serialized)

    def test_cli_roundtrip_and_fail_closed_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "snapshot.json"
            out_path = Path(tmp) / "report.json"
            in_path.write_text(json.dumps(_snapshot([_ready_item(7001)])), encoding="utf-8")
            stdout = io.StringIO()
            with patch("sys.argv", ["work_supply_capacity", "--input", str(in_path), "--output", str(out_path)]):
                with redirect_stdout(stdout):
                    rc = main()
            self.assertEqual(0, rc)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(1, report["verified_ready_count"])
            self.assertFalse(report["dispatch_allowed"])

            missing = Path(tmp) / "missing.json"
            err_stdout = io.StringIO()
            with patch("sys.argv", ["work_supply_capacity", "--input", str(missing)]):
                with redirect_stdout(err_stdout):
                    rc_err = main()
            self.assertEqual(2, rc_err)
            err_report = json.loads(err_stdout.getvalue())
            self.assertFalse(err_report["complete"])
            self.assertIsNone(err_report["verified_ready_count"])
            self.assertEqual("UNKNOWN", err_report["ready_replenishment_status"])


if __name__ == "__main__":
    unittest.main()
