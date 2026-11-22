"""Regression tests for #943 read-only single-candidate inventory evidence."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.queue_owner_inventory_pilot import inspect_one_candidate, main


class OwnerInventoryPilotTests(unittest.TestCase):
    def setUp(self):
        self.issues = [{"number": 1000, "allowed_paths": ["scripts/alpha.py"],
                        "owner_slice": "issue-1000"}]
        self.prs = {"complete": True, "prs": [{"number": 2000, "paths": ["scripts/beta.py"]}]}

    def test_even_complete_pr_inventory_does_not_authorize_dispatch(self):
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("HOLD", result["status"])
        self.assertEqual("OWNER_ISSUER_UNVERIFIED", result["reason"])
        self.assertFalse(result["dispatch_allowed"])
        self.assertEqual(1000, result["selected_issue"])

    def test_missing_open_pr_inventory_is_hold(self):
        result = inspect_one_candidate(self.issues, None)
        self.assertEqual("PR_PATH_INVENTORY_INCOMPLETE", result["reason"])
        self.assertFalse(result["dispatch_allowed"])

    def test_pr_path_conflict_is_hold(self):
        self.prs["prs"][0]["paths"] = ["scripts/alpha.py"]
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("PR_PATH_CONFLICT", result["reason"])
        self.assertEqual([2000], result["conflicting_prs"])
        self.assertFalse(result["dispatch_allowed"])

    def test_glob_path_conflict_is_hold(self):
        self.issues[0]["allowed_paths"] = ["scripts/**"]
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("PR_PATH_CONFLICT", result["reason"])

    def test_bare_directory_scope_conflicts_with_file(self):
        self.issues[0]["allowed_paths"] = ["scripts"]
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("PR_PATH_CONFLICT", result["reason"])
        self.assertEqual([2000], result["conflicting_prs"])

    def test_pr_bare_directory_conflicts_with_candidate_file(self):
        self.prs["prs"][0]["paths"] = ["scripts"]
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("PR_PATH_CONFLICT", result["reason"])

    def test_similar_file_prefix_is_not_conflict(self):
        self.prs["prs"][0]["paths"] = ["scripts/alpha.py.bak"]
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("OWNER_ISSUER_UNVERIFIED", result["reason"])

    def test_output_write_failure_fails_closed_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues = Path(tmp) / "issues.json"
            prs = Path(tmp) / "prs.json"
            issues.write_text(json.dumps(self.issues), encoding="utf-8")
            prs.write_text(json.dumps(self.prs), encoding="utf-8")
            output = Path(tmp) / "missing-directory" / "report.json"
            stdout = io.StringIO()
            with patch("sys.argv", ["pilot", "--issues", str(issues),
                                    "--open-prs", str(prs), "--output", str(output)]):
                with redirect_stdout(stdout):
                    rc = main()
            self.assertEqual(2, rc)
            self.assertFalse(output.exists())
            report = json.loads(stdout.getvalue())
            self.assertEqual("HOLD", report["status"])
            self.assertEqual("OUTPUT_UNAVAILABLE", report["reason"])
            self.assertFalse(report["dispatch_allowed"])

    def test_issue_79_is_never_candidate(self):
        result = inspect_one_candidate(
            [{"number": 79, "allowed_paths": ["scripts/alpha.py"], "owner_slice": "issue-79"}],
            self.prs,
        )
        self.assertEqual("NO_READY_CANDIDATE", result["reason"])
        self.assertIsNone(result["selected_issue"])
        self.assertFalse(result["dispatch_allowed"])

    def test_invalid_or_ambiguous_pr_path_inventory_holds(self):
        self.prs["prs"][0]["paths"] = []
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("PR_PATH_INVENTORY_INCOMPLETE", result["reason"])
        self.assertFalse(result["dispatch_allowed"])

    def test_missing_issuer_and_owner_scope_holds(self):
        self.issues[0]["owner_slice"] = ""
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("OWNER_SLICE_UNVERIFIED", result["reason"])
        self.assertFalse(result["dispatch_allowed"])

    def test_missing_candidate_path_holds(self):
        self.issues[0]["allowed_paths"] = []
        result = inspect_one_candidate(self.issues, self.prs)
        self.assertEqual("ISSUE_PATH_SCOPE_UNVERIFIED", result["reason"])

    def test_no_ready_issue_holds(self):
        self.assertEqual("NO_READY_CANDIDATE",
                         inspect_one_candidate([], self.prs)["reason"])

    def test_untrusted_claims_are_not_considered_attestation(self):
        issue = dict(self.issues[0], issuer_authenticated=True,
                     owner_inventory_complete=True, lease_status="ACTIVE")
        result = inspect_one_candidate([issue], self.prs)
        self.assertEqual("OWNER_ISSUER_UNVERIFIED", result["reason"])
        self.assertFalse(result["dispatch_allowed"])


if __name__ == "__main__":
    unittest.main()
