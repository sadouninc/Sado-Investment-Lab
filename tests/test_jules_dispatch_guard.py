import unittest

from scripts.jules_dispatch_guard import DispatchControl, build_prompt, decide, is_target_ready, parse_control


class JulesDispatchGuardTest(unittest.TestCase):
    def test_parse_control(self):
        body = """## STATE
READY_FOR_SCHEDULED_RUN

## CURRENT RUN
- ACTIVE RUN TOKEN: `jules-daily-688-sony-owner-view-v1`
- TARGET: #688 — Sony Owner View
"""
        control = parse_control(body)
        self.assertEqual(control.state, "READY_FOR_SCHEDULED_RUN")
        self.assertEqual(control.run_token, "jules-daily-688-sony-owner-view-v1")
        self.assertEqual(control.target_issue, 688)

    def test_parse_control_tolerates_heading_whitespace_and_crlf(self):
        body = (
            "##\tSTATE   \r\n"
            "  READY_FOR_SCHEDULED_RUN\r\n\r\n"
            "## CURRENT RUN\r\n"
            "- ACTIVE RUN TOKEN: `token-crlf`\r\n"
            "- TARGET: #688 — Sony Owner View\r\n"
        )
        control = parse_control(body)
        self.assertEqual(control.state, "READY_FOR_SCHEDULED_RUN")
        self.assertEqual(control.run_token, "token-crlf")
        self.assertEqual(control.target_issue, 688)

    def test_noncanonical_state_heading_fails_closed(self):
        body = """## STATE Notes
READY_FOR_SCHEDULED_RUN
- ACTIVE RUN TOKEN: `token`
- TARGET: #688
"""
        control = parse_control(body)
        self.assertEqual(control.state, "")
        result = decide(
            control,
            secret_present=True,
            target_open=True,
            target_ready=True,
            overlapping_pr=False,
        )
        self.assertEqual(result, "SYNC_UNVERIFIED_NOOP")

    def test_stop_is_noop_even_with_secret(self):
        result = decide(
            DispatchControl("STOP", "token", 688),
            secret_present=True,
            target_open=True,
            target_ready=True,
            overlapping_pr=False,
        )
        self.assertEqual(result, "STOP_NOOP")

    def test_missing_secret_is_fail_closed(self):
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688),
            secret_present=False,
            target_open=True,
            target_ready=True,
            overlapping_pr=False,
        )
        self.assertEqual(result, "MISSING_SECRET_NOOP")

    def test_issue_79_is_hard_denied(self):
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 79),
            secret_present=True,
            target_open=True,
            target_ready=True,
            overlapping_pr=False,
        )
        self.assertEqual(result, "FORBIDDEN_TARGET_NOOP")

    def test_stale_token_is_noop(self):
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "same", 688),
            secret_present=True,
            target_open=True,
            target_ready=True,
            overlapping_pr=False,
            last_consumed_run_token="same",
        )
        self.assertEqual(result, "STALE_RUN_TOKEN_NOOP")

    def test_closed_or_not_ready_target_is_duplicate_noop(self):
        for target_open, target_ready in ((False, True), (True, False)):
            with self.subTest(target_open=target_open, target_ready=target_ready):
                result = decide(
                    DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688),
                    secret_present=True,
                    target_open=target_open,
                    target_ready=target_ready,
                    overlapping_pr=False,
                )
                self.assertEqual(result, "DUPLICATE_TARGET_NOOP")

    def test_path_overlap_is_fail_closed(self):
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688),
            secret_present=True,
            target_open=True,
            target_ready=True,
            overlapping_pr=True,
        )
        self.assertEqual(result, "PATH_CONFLICT_NOOP")

    def test_only_clean_ready_case_dispatches(self):
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688),
            secret_present=True,
            target_open=True,
            target_ready=True,
            overlapping_pr=False,
        )
        self.assertEqual(result, "DISPATCH_ALLOWED")

    def test_prompt_repeats_safety_boundaries(self):
        prompt = build_prompt("control", "target")
        self.assertIn("exactly one task", prompt)
        self.assertIn("Never modify Issue #79", prompt)
        self.assertIn("Never merge", prompt)
        self.assertIn("non-empty diff", prompt)
        self.assertIn("duplicate/path/owner-conflict", prompt)


class TargetReadinessTest(unittest.TestCase):
    """Test suite for canonical readiness detection - fail-closed on ambiguity."""

    def work_contract(self, *, status="READY_FOR_IMPLEMENTATION", risk="GREEN"):
        """Helper to build valid Work Contract YAML block."""
        return f'''```yaml
work_contract:
  version: 1
  goal: "test goal"
  status: {status}
  owner_slice: "test-slice"
  risk: {risk}
  authority: STANDARD
  dependencies: []
  allowed_paths: ["scripts/**"]
  forbidden_paths: [".github/**"]
  acceptance_tests: ["pytest tests/"]
  expected_outputs: ["PR"]
  human_gate: ["merge"]
  non_goals: []
```'''

    def issue_json(self, body="", labels=None, comments=None):
        """Helper to build GitHub Issue JSON payload."""
        return {
            "number": 999,
            "state": "open",
            "body": body,
            "labels": labels or [],
            "comments": comments or [],
        }

    def test_canonical_ready_label_status_ready(self):
        """Canonical label status:ready => ready."""
        target = self.issue_json(labels=[{"name": "status:ready"}])
        self.assertTrue(is_target_ready(target))

    def test_canonical_ready_label_work_ready(self):
        """Canonical label work:ready => ready."""
        target = self.issue_json(labels=[{"name": "work:ready"}])
        self.assertTrue(is_target_ready(target))

    def test_canonical_work_contract_ready_status(self):
        """Valid Work Contract with READY_FOR_IMPLEMENTATION status => ready."""
        target = self.issue_json(body=self.work_contract(status="READY_FOR_IMPLEMENTATION"))
        self.assertTrue(is_target_ready(target))

    def test_work_contract_non_ready_status_not_ready(self):
        """Work Contract with non-ready status => not ready."""
        target = self.issue_json(body=self.work_contract(status="DESIGNING"))
        self.assertFalse(is_target_ready(target))

    def test_malformed_contract_fails_closed(self):
        """Malformed contract => fail closed (not ready)."""
        target = self.issue_json(body="```yaml\nwork_contract:\n  invalid yaml [[\n```")
        self.assertFalse(is_target_ready(target))

    def test_missing_contract_and_no_labels_not_ready(self):
        """No contract, no labels => not ready."""
        target = self.issue_json(body="Just a regular issue description")
        self.assertFalse(is_target_ready(target))

    def test_historical_comment_ready_but_current_body_not_ready(self):
        """Historical comment contains READY_FOR_IMPLEMENTATION but current state is not ready => not ready.
        
        This is the core fix: historical comments must not resurrect readiness.
        """
        comments = [
            {"body": "This was READY_FOR_IMPLEMENTATION last week", "created_at": "2024-01-01"},
            {"body": "Status: READY_FOR_IMPLEMENTATION", "created_at": "2024-01-02"},
        ]
        # Current body has no ready state
        target = self.issue_json(body="Current issue body with no ready markers", comments=comments)
        self.assertFalse(is_target_ready(target))

    def test_quoted_ready_in_body_not_ready(self):
        """Quoted/sample READY_FOR_IMPLEMENTATION in prose => not ready.
        
        Example: Documentation showing the status format.
        """
        body = '''
## How to mark ready

Set the status to `READY_FOR_IMPLEMENTATION` when done.

Example:
```
Status: READY_FOR_IMPLEMENTATION
```
'''
        target = self.issue_json(body=body)
        self.assertFalse(is_target_ready(target))

    def test_negative_ready_mention_not_ready(self):
        """Negative mention like 'NOT READY_FOR_IMPLEMENTATION' => not ready."""
        body = "This is NOT READY_FOR_IMPLEMENTATION yet, still in design phase."
        target = self.issue_json(body=body)
        self.assertFalse(is_target_ready(target))

    def test_prose_ready_substring_without_structure_not_ready(self):
        """Prose containing READY_FOR_IMPLEMENTATION substring without structure => not ready."""
        body = "We should make this READY_FOR_IMPLEMENTATION soon but not today."
        target = self.issue_json(body=body)
        self.assertFalse(is_target_ready(target))

    def test_multiple_contracts_ambiguous_fails_closed(self):
        """Multiple work_contract blocks => ambiguous, fail closed."""
        body = self.work_contract(status="READY_FOR_IMPLEMENTATION") + "\n\n" + self.work_contract(status="DESIGNING")
        target = self.issue_json(body=body)
        self.assertFalse(is_target_ready(target))

    def test_label_overrides_non_ready_contract(self):
        """If label is ready, ignore non-ready contract (labels are checked first)."""
        target = self.issue_json(
            body=self.work_contract(status="DESIGNING"),
            labels=[{"name": "status:ready"}]
        )
        self.assertTrue(is_target_ready(target))

    def test_empty_body_no_labels_not_ready(self):
        """Empty body, no labels => not ready."""
        target = self.issue_json(body="")
        self.assertFalse(is_target_ready(target))

    def test_none_body_no_labels_not_ready(self):
        """None body (missing), no labels => not ready."""
        target = {"number": 999, "state": "open", "labels": []}
        self.assertFalse(is_target_ready(target))


class EndToEndDispatchTest(unittest.TestCase):
    """End-to-end tests combining readiness detection with dispatch decision."""

    def work_contract(self, status="READY_FOR_IMPLEMENTATION"):
        return f'''```yaml
work_contract:
  version: 1
  goal: "e2e test"
  status: {status}
  owner_slice: "e2e-slice"
  risk: GREEN
  authority: STANDARD
  dependencies: []
  allowed_paths: ["scripts/**"]
  forbidden_paths: []
  acceptance_tests: ["pytest"]
  expected_outputs: ["PR"]
  human_gate: ["merge"]
  non_goals: []
```'''

    def test_historical_ready_comment_current_non_ready_results_in_noop(self):
        """Historical comment with READY + current non-ready state => NOOP."""
        target = {
            "state": "open",
            "body": "Current body without ready state",
            "labels": [],
            "comments": [{"body": "Was READY_FOR_IMPLEMENTATION"}],
        }
        ready = is_target_ready(target)
        self.assertFalse(ready)
        
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688),
            secret_present=True,
            target_open=True,
            target_ready=ready,
            overlapping_pr=False,
        )
        self.assertEqual(result, "DUPLICATE_TARGET_NOOP")

    def test_canonical_label_all_guards_pass_dispatches(self):
        """Canonical label + all other guards pass => DISPATCH_ALLOWED."""
        target = {"state": "open", "body": "", "labels": [{"name": "work:ready"}]}
        ready = is_target_ready(target)
        self.assertTrue(ready)
        
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688),
            secret_present=True,
            target_open=True,
            target_ready=ready,
            overlapping_pr=False,
        )
        self.assertEqual(result, "DISPATCH_ALLOWED")

    def test_canonical_work_contract_all_guards_pass_dispatches(self):
        """Canonical Work Contract READY + all guards pass => DISPATCH_ALLOWED."""
        target = {"state": "open", "body": self.work_contract("READY_FOR_IMPLEMENTATION"), "labels": []}
        ready = is_target_ready(target)
        self.assertTrue(ready)
        
        result = decide(
            DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688),
            secret_present=True,
            target_open=True,
            target_ready=ready,
            overlapping_pr=False,
        )
        self.assertEqual(result, "DISPATCH_ALLOWED")


if __name__ == "__main__":
    unittest.main()
