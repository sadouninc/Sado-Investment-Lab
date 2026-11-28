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

_UNSET = object()


def _ready_item(
    issue: int,
    *,
    state: str = "READY",
    owner_slice: str | None = None,
    allowed_paths: list[str] | None = None,
    dependencies_satisfied: bool = True,
    stop_clear: bool = True,
    updated_at: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
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


def _snapshot(
    items: list[dict[str, Any]],
    *,
    complete: bool = True,
    open_prs: Any = _UNSET,
    as_of: str | None = "2026-11-28T12:00:00Z",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
        self.assertEqual(0, result["prepared_lower_bound"])
        self.assertEqual(0, result["verified_ready_count"])
        self.assertEqual(0, result["verified_ready_lower_bound"])
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
            self.assertIsNone(result["verified_ready_lower_bound"])
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
                    {"number": 500, "paths": ["scripts/a.py"], "linked_issues": [], "wait_state": "REVIEW_WAIT"},
                    {"number": 500, "paths": ["scripts/b.py"], "linked_issues": [], "wait_state": "REVIEW_WAIT"},
                ],
            },
        )
        res_prs = classify_work_supply_capacity(dup_prs)
        self.assertFalse(res_prs["complete"])
        self.assertIsNone(res_prs["verified_ready_count"])
        self.assertEqual([500], res_prs["diagnostics"]["duplicate_prs"])

    def test_issue_79_and_79_only_pr_exclusion_with_conservative_path_guard(self):
        snap = _snapshot(
            [
                _ready_item(79),
                _ready_item(1010),
                _ready_item(1011, allowed_paths=["scripts/shared_79.py"]),
            ],
            open_prs={
                "complete": True,
                "prs": [
                    {
                        "number": 790,
                        "paths": ["scripts/shared_79.py"],
                        "linked_issues": [79],
                        "wait_state": "REVIEW_WAIT",
                    }
                ],
            },
        )
        result = classify_work_supply_capacity(snap)
        self.assertEqual(2, result["prepared_count"])
        self.assertEqual(1, result["verified_ready_count"])
        self.assertEqual([1010], result["issues_by_bucket"]["verified_ready"])
        self.assertEqual([1011], result["issues_by_bucket"]["dependency_path_blocked"])
        self.assertEqual(0, result["counts"]["ci_review_merge_wait"])
        self.assertEqual([], result["open_prs_by_bucket"]["ci_review_merge_wait"])
        self.assertEqual([], result["open_pr_classifications"])
        self.assertEqual(1, result["diagnostics"]["excluded_issue_79_count"])
        self.assertEqual(1, result["diagnostics"]["excluded_issue_79_pr_count"])
        self.assertTrue(result["issue_79_excluded"])
        for items in result["issues_by_bucket"].values():
            self.assertNotIn(79, items)

    def test_issue_79_forward_only_pr_link_is_excluded_and_contradictions_fail_closed(self):
        item_79 = _ready_item(79)
        item_79["open_pr"] = 791
        snap = _snapshot(
            [
                item_79,
                _ready_item(1020),
                _ready_item(1021, allowed_paths=["scripts/shared_79_forward.py"]),
            ],
            open_prs={
                "complete": True,
                "prs": [
                    {
                        "number": 791,
                        "paths": ["scripts/shared_79_forward.py"],
                        "linked_issues": [],
                        "wait_state": "REVIEW_WAIT",
                    }
                ],
            },
        )
        result = classify_work_supply_capacity(snap)
        self.assertTrue(result["complete"])
        self.assertEqual(2, result["prepared_count"])
        self.assertEqual(1, result["verified_ready_count"])
        self.assertEqual([1020], result["issues_by_bucket"]["verified_ready"])
        self.assertEqual([1021], result["issues_by_bucket"]["dependency_path_blocked"])
        self.assertEqual(0, result["counts"]["ci_review_merge_wait"])
        self.assertEqual([], result["open_prs_by_bucket"]["ci_review_merge_wait"])
        self.assertEqual([], result["open_pr_classifications"])
        self.assertEqual(1, result["diagnostics"]["excluded_issue_79_count"])
        self.assertEqual(1, result["diagnostics"]["excluded_issue_79_pr_count"])

        contradiction = _snapshot(
            [item_79, _ready_item(1022)],
            open_prs={
                "complete": True,
                "prs": [
                    {
                        "number": 791,
                        "paths": ["scripts/shared_79_forward.py"],
                        "linked_issues": [1022],
                        "wait_state": "REVIEW_WAIT",
                    }
                ],
            },
        )
        contradiction_res = classify_work_supply_capacity(contradiction)
        self.assertFalse(contradiction_res["complete"])
        self.assertIsNone(contradiction_res["verified_ready_count"])
        self.assertEqual("UNKNOWN", contradiction_res["ready_replenishment_status"])

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

    def test_explicit_open_pr_reconciles_with_empty_pr_linked_issues_without_double_count(self):
        linked_item = _ready_item(2101, state="READY")
        linked_item["open_pr"] = 910
        snap = _snapshot(
            [linked_item],
            open_prs={
                "complete": True,
                "prs": [
                    {
                        "number": 910,
                        "paths": ["scripts/mod_2101.py"],
                        "linked_issues": [],
                        "wait_state": "CI_WAIT",
                        "updated_at": "2026-11-28T10:00:00Z",
                    }
                ],
            },
        )
        result = classify_work_supply_capacity(snap)
        self.assertEqual(0, result["prepared_count"])
        self.assertEqual(0, result["verified_ready_count"])
        self.assertEqual(1, result["counts"]["ci_review_merge_wait"])
        self.assertEqual([2101], result["issues_by_bucket"]["ci_review_merge_wait"])
        self.assertEqual([2101], result["open_pr_classifications"][0]["linked_issues"])

    def test_malformed_open_pr_link_and_missing_linked_issues_fail_closed(self):
        for bad_open_pr in ("901", True, 0, -5, 999):
            item = _ready_item(2201, state="READY")
            item["open_pr"] = bad_open_pr
            result = classify_work_supply_capacity(_snapshot([item]))
            self.assertTrue(result["complete"])
            self.assertIsNone(result["verified_ready_count"])
            self.assertEqual(0, result["verified_ready_lower_bound"])
            self.assertEqual("UNKNOWN", result["ready_replenishment_status"])
            self.assertEqual([2201], result["issues_by_bucket"]["unknown"])

        for bad_prs in (
            {"complete": True, "prs": [{"number": 920, "paths": ["scripts/x.py"]}]},
            {"complete": True, "prs": [{"number": 920, "paths": ["scripts/x.py"], "linked_issues": None}]},
        ):
            res = classify_work_supply_capacity(_snapshot([_ready_item(2202)], open_prs=bad_prs))
            self.assertFalse(res["complete"])
            self.assertIsNone(res["verified_ready_count"])
            self.assertEqual("UNKNOWN", res["ready_replenishment_status"])

    def test_missing_evidence_suppresses_starvation_and_distinguishes_lower_bound(self):
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
        self.assertTrue(result["complete"])
        self.assertIsNone(result["prepared_count"])
        self.assertEqual(0, result["prepared_lower_bound"])
        self.assertIsNone(result["verified_ready_count"])
        self.assertEqual(0, result["verified_ready_lower_bound"])
        self.assertEqual("UNKNOWN", result["prepared_status"])
        self.assertEqual("UNKNOWN", result["ready_replenishment_status"])
        self.assertEqual(4, result["counts"]["unknown"])
        self.assertEqual([3001, 3002, 3003, 3004], result["issues_by_bucket"]["unknown"])
        self.assertTrue(result["diagnostics"]["readiness_uncertainty"])

    def test_active_implementation_missing_owner_or_paths_blocks_verified_ready(self):
        active_missing_owner = _ready_item(3501, state="IMPLEMENTING", owner_slice="")
        active_missing_paths = _ready_item(3502, state="IMPLEMENTING", allowed_paths=[])
        ready_candidate = _ready_item(3503, state="READY")

        for active_item in (active_missing_owner, active_missing_paths):
            result = classify_work_supply_capacity(_snapshot([active_item, ready_candidate]))
            self.assertTrue(result["complete"])
            self.assertTrue(result["diagnostics"]["active_conflict_inventory_unknown"])
            self.assertIsNone(result["verified_ready_count"])
            self.assertEqual(0, result["verified_ready_lower_bound"])
            self.assertEqual("UNKNOWN", result["ready_replenishment_status"])
            self.assertEqual([3503], result["issues_by_bucket"]["unknown"])
            self.assertEqual([active_item["issue"]], result["issues_by_bucket"]["active_implementation"])

    def test_linked_pr_active_state_enforces_owner_conflict_and_missing_owner_uncertainty(self):
        # Case 1: Item A has stale READY state, linked via reverse PR with REVISION_REQUIRED,
        # same owner as Item B with disjoint paths -> B must be blocked, not VERIFIED_READY.
        item_a = _ready_item(3601, state="READY", owner_slice="same", allowed_paths=["scripts/a.py"])
        item_b = _ready_item(3602, state="READY", owner_slice="same", allowed_paths=["scripts/b.py"])
        prs = {
            "complete": True,
            "prs": [
                {
                    "number": 961,
                    "paths": ["scripts/a.py"],
                    "linked_issues": [3601],
                    "wait_state": "REVISION_REQUIRED",
                }
            ],
        }
        same_owner_res = classify_work_supply_capacity(_snapshot([item_a, item_b], open_prs=prs))
        self.assertTrue(same_owner_res["complete"])
        self.assertEqual([3601], same_owner_res["issues_by_bucket"]["active_implementation"])
        self.assertEqual([3602], same_owner_res["issues_by_bucket"]["dependency_path_blocked"])
        self.assertEqual(0, same_owner_res["verified_ready_count"])
        self.assertEqual([], same_owner_res["issues_by_bucket"]["verified_ready"])

        # Case 2: Linked PR active item missing owner_slice -> B cannot attest non-conflict -> UNKNOWN.
        item_a_missing = _ready_item(3601, state="READY", owner_slice="", allowed_paths=["scripts/a.py"])
        missing_owner_res = classify_work_supply_capacity(
            _snapshot([item_a_missing, item_b], open_prs=prs)
        )
        self.assertTrue(missing_owner_res["complete"])
        self.assertTrue(missing_owner_res["diagnostics"]["active_conflict_inventory_unknown"])
        self.assertIsNone(missing_owner_res["verified_ready_count"])
        self.assertEqual("UNKNOWN", missing_owner_res["ready_replenishment_status"])
        self.assertEqual([3602], missing_owner_res["issues_by_bucket"]["unknown"])

    def test_dependency_and_path_conflicts_block_ready_but_keep_prepared_count(self):
        dep_blocked = _ready_item(4001, dependencies_satisfied=False)
        pr_path_conflict = _ready_item(4002, allowed_paths=["scripts/shared.py"])
        active_impl = _ready_item(
            4003,
            state="IMPLEMENTING",
            owner_slice="sora-active",
            allowed_paths=["scripts/active.py"],
        )
        active_conflict = _ready_item(4004, allowed_paths=["scripts/active.py"])
        next_item = _ready_item(4005, state="NEXT")

        snap = _snapshot(
            [dep_blocked, pr_path_conflict, active_impl, active_conflict, next_item],
            open_prs={
                "complete": True,
                "prs": [
                    {
                        "number": 950,
                        "paths": ["scripts/shared.py"],
                        "linked_issues": [],
                        "wait_state": "CI_WAIT",
                    }
                ],
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

    def test_no_wall_clock_assumption_extreme_dates_and_no_raw_text_leak(self):
        item = _ready_item(6001, state="REVIEW_WAIT", updated_at="2026-11-28T06:00:00Z")
        item["body"] = "SENSITIVE_RAW_ISSUE_BODY_SHOULD_NOT_APPEAR"
        item["secret_token"] = "gho_should_not_appear"
        without_as_of = classify_work_supply_capacity(_snapshot([item], as_of=None))
        self.assertFalse(without_as_of["age_summary"]["as_of_valid"])
        self.assertIsNone(without_as_of["item_classifications"][0]["age_hours"])
        serialized = json.dumps(without_as_of)
        self.assertNotIn("SENSITIVE_RAW_ISSUE_BODY_SHOULD_NOT_APPEAR", serialized)
        self.assertNotIn("gho_should_not_appear", serialized)

        extreme = _ready_item(6002, state="REVIEW_WAIT", updated_at="0001-01-01T00:00:00+14:00")
        res_extreme = classify_work_supply_capacity(_snapshot([extreme]))
        self.assertIsNone(res_extreme["item_classifications"][0]["age_hours"])

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
