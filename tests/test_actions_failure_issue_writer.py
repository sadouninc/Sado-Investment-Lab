"""No-network tests for the gated Issue #873 writer."""
import unittest
from unittest.mock import patch

from scripts.actions_failure_analyzer import build_issue_draft
from scripts.actions_failure_issue_writer import IssueWriteError, post_validated_issue


class WriterTests(unittest.TestCase):
    def setUp(self):
        analysis = {
            "request_id": "actions-failure-" + "b" * 20,
            "source_run_id": 101,
            "job_id": 202,
            "reproduction_evidence": "https://github.com/acme/repo/actions/runs/101/job/202",
            "evidence_status": "OBSERVED_FAILURE_ROOT_CAUSE_UNVERIFIED",
            "error_class": "TEST_FAILURE",
            "workflow_name": "CI",
            "failing_step": "pytest",
            "candidate_root_cause": "hypothesis",
            "next_minimal_fix": "check logs",
        }
        self.result = {"decision": "ISSUE_DRAFT_ELIGIBLE", "analysis": analysis, "issue_draft": build_issue_draft(analysis)}

    @patch("scripts.actions_failure_issue_writer.urlopen")
    def test_default_deny_no_network(self, urlopen):
        with self.assertRaises(IssueWriteError):
            post_validated_issue("acme/repo", "token", self.result, [], inventory_complete=True)
        urlopen.assert_not_called()

    @patch("scripts.actions_failure_issue_writer.urlopen")
    def test_missing_token_no_network(self, urlopen):
        with self.assertRaises(IssueWriteError):
            post_validated_issue("acme/repo", "", self.result, [], inventory_complete=True, enable_post=True)
        urlopen.assert_not_called()

    @patch("scripts.actions_failure_issue_writer.urlopen")
    def test_duplicate_no_network(self, urlopen):
        with self.assertRaises(ValueError):
            post_validated_issue("acme/repo", "token", self.result, [{"number": 33, "body": self.result["issue_draft"]["body"]}], inventory_complete=True, enable_post=True)
        urlopen.assert_not_called()

    @patch("scripts.actions_failure_issue_writer.urlopen")
    def test_incomplete_inventory_no_network(self, urlopen):
        with self.assertRaises(ValueError):
            post_validated_issue("acme/repo", "token", self.result, [], inventory_complete=False, enable_post=True)
        urlopen.assert_not_called()

    @patch("scripts.actions_failure_issue_writer.urlopen")
    def test_invalid_repo_no_network(self, urlopen):
        with self.assertRaises(IssueWriteError):
            post_validated_issue("acme/repo/other", "token", self.result, [], inventory_complete=True, enable_post=True)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
