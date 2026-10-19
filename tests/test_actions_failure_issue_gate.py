"""Tests for fail-closed Issue #873 payload validation."""
import unittest

from scripts.actions_failure_analyzer import build_issue_draft
from scripts.actions_failure_issue_gate import IssuePostRejected, validate_issue_proposal


class IssueGateTests(unittest.TestCase):
    def setUp(self):
        self.analysis = {
            "request_id": "actions-failure-" + "a" * 20,
            "source_run_id": 123,
            "job_id": 456,
            "reproduction_evidence": "https://github.com/acme/repo/actions/runs/123/job/456",
            "evidence_status": "OBSERVED_FAILURE_ROOT_CAUSE_UNVERIFIED",
            "error_class": "TEST_FAILURE",
            "workflow_name": "CI",
            "failing_step": "pytest",
            "candidate_root_cause": "hypothesis",
            "next_minimal_fix": "check logs",
        }
        self.result = {"decision": "ISSUE_DRAFT_ELIGIBLE", "analysis": self.analysis, "issue_draft": build_issue_draft(self.analysis)}

    def check_rejected(self, result=None, issues=None, complete=True):
        with self.assertRaises(IssuePostRejected):
            validate_issue_proposal(self.result if result is None else result, [] if issues is None else issues, inventory_complete=complete)

    def test_valid_proposal(self):
        payload = validate_issue_proposal(self.result, [], inventory_complete=True)
        self.assertIn(self.analysis["request_id"], payload["body"])
        self.assertEqual(set(payload), {"title", "body"})

    def test_duplicate_suppressed(self):
        self.check_rejected(issues=[{"number": 123, "body": self.result["issue_draft"]["body"]}])

    def test_incomplete_inventory(self):
        self.check_rejected(complete=False)

    def test_noneligible_decision(self):
        self.check_rejected(result={**self.result, "decision": "HOLD_INCOMPLETE_INVENTORY"})

    def test_empty_result_rejected(self):
        self.check_rejected(result={})

    def test_conflicting_state_rejected(self):
        draft = self.result["issue_draft"]
        body = draft["body"] + "\n- 状態: READY_FOR_IMPLEMENTATION"
        self.check_rejected(result={**self.result, "issue_draft": {**draft, "body": body}})

    def test_missing_draft(self):
        self.check_rejected(result={**self.result, "issue_draft": None})

    def test_invalid_evidence(self):
        self.check_rejected(result={**self.result, "analysis": {**self.analysis, "reproduction_evidence": "https://example.com"}})

    def test_invalid_request_id(self):
        self.check_rejected(result={**self.result, "analysis": {**self.analysis, "request_id": "bad"}})

    def test_missing_marker(self):
        self.check_rejected(result={**self.result, "issue_draft": {**self.result["issue_draft"], "body": "TRIAGE_REQUIRED READY_FOR_IMPLEMENTATION"}})

    def test_missing_triage(self):
        self.check_rejected(result={**self.result, "issue_draft": {**self.result["issue_draft"], "body": "<!-- " + self.analysis["request_id"] + " -->"}})


if __name__ == "__main__":
    unittest.main()
