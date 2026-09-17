import unittest

from scripts.jules_dispatch_guard import DispatchControl, build_prompt, decide, parse_control, target_is_ready


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
        body = "##\tSTATE   \r\n  READY_FOR_SCHEDULED_RUN\r\n- ACTIVE RUN TOKEN: `token-crlf`\r\n- TARGET: #688\r\n"
        control = parse_control(body)
        self.assertEqual(control.state, "READY_FOR_SCHEDULED_RUN")
        self.assertEqual(control.run_token, "token-crlf")
        self.assertEqual(control.target_issue, 688)

    def test_noncanonical_state_heading_fails_closed(self):
        control = parse_control("## STATE Notes\nREADY_FOR_SCHEDULED_RUN\n- ACTIVE RUN TOKEN: `token`\n- TARGET: #688\n")
        self.assertEqual(control.state, "")
        self.assertEqual(decide(control, secret_present=True, target_open=True, target_ready=True, overlapping_pr=False), "SYNC_UNVERIFIED_NOOP")

    def test_historical_ready_comment_is_not_authority(self):
        target = {"body": "Status: NOT_READY", "labels": [], "comments": [{"body": "READY_FOR_IMPLEMENTATION"}]}
        self.assertFalse(target_is_ready(target))

    def test_quoted_or_negative_ready_prose_is_not_authority(self):
        for body in ('Example: "READY_FOR_IMPLEMENTATION"', "NOT READY_FOR_IMPLEMENTATION"):
            with self.subTest(body=body):
                self.assertFalse(target_is_ready({"body": body, "labels": []}))

    def test_canonical_ready_label_is_authority(self):
        self.assertTrue(target_is_ready({"body": "not ready prose", "labels": [{"name": "status:ready"}]}))
        self.assertTrue(target_is_ready({"body": "", "labels": [{"name": "work:ready"}]}))

    def test_canonical_work_contract_is_authority(self):
        body = """```yaml
work_contract:
  version: 1
  goal: "bounded work"
  status: READY_FOR_IMPLEMENTATION
  owner_slice: "slice"
  risk: YELLOW
  authority: STANDARD
  dependencies: []
  allowed_paths: ["scripts/example.py"]
  forbidden_paths: ["Issue #79"]
  acceptance_tests: ["pytest"]
  expected_outputs: ["PR"]
  human_gate: ["review"]
  non_goals: ["automatic trading"]
```"""
        self.assertTrue(target_is_ready({"body": body, "labels": []}))

    def test_malformed_or_multiple_contract_fails_closed(self):
        malformed = "```yaml\nwork_contract:\n  status: READY_FOR_IMPLEMENTATION\n```"
        multiple = malformed + "\n" + malformed
        self.assertFalse(target_is_ready({"body": malformed, "labels": []}))
        self.assertFalse(target_is_ready({"body": multiple, "labels": []}))

    def test_stop_is_noop_even_with_secret(self):
        result = decide(DispatchControl("STOP", "token", 688), secret_present=True, target_open=True, target_ready=True, overlapping_pr=False)
        self.assertEqual(result, "STOP_NOOP")

    def test_missing_secret_is_fail_closed(self):
        result = decide(DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688), secret_present=False, target_open=True, target_ready=True, overlapping_pr=False)
        self.assertEqual(result, "MISSING_SECRET_NOOP")

    def test_issue_79_is_hard_denied(self):
        result = decide(DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 79), secret_present=True, target_open=True, target_ready=True, overlapping_pr=False)
        self.assertEqual(result, "FORBIDDEN_TARGET_NOOP")

    def test_stale_token_is_noop(self):
        result = decide(DispatchControl("READY_FOR_SCHEDULED_RUN", "same", 688), secret_present=True, target_open=True, target_ready=True, overlapping_pr=False, last_consumed_run_token="same")
        self.assertEqual(result, "STALE_RUN_TOKEN_NOOP")

    def test_closed_or_not_ready_target_is_duplicate_noop(self):
        for target_open, target_ready in ((False, True), (True, False)):
            with self.subTest(target_open=target_open, target_ready=target_ready):
                result = decide(DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688), secret_present=True, target_open=target_open, target_ready=target_ready, overlapping_pr=False)
                self.assertEqual(result, "DUPLICATE_TARGET_NOOP")

    def test_path_overlap_is_fail_closed(self):
        result = decide(DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688), secret_present=True, target_open=True, target_ready=True, overlapping_pr=True)
        self.assertEqual(result, "PATH_CONFLICT_NOOP")

    def test_only_clean_ready_case_dispatches(self):
        result = decide(DispatchControl("READY_FOR_SCHEDULED_RUN", "token", 688), secret_present=True, target_open=True, target_ready=True, overlapping_pr=False)
        self.assertEqual(result, "DISPATCH_ALLOWED")

    def test_prompt_repeats_safety_boundaries(self):
        prompt = build_prompt("control", "target")
        self.assertIn("exactly one task", prompt)
        self.assertIn("Never modify Issue #79", prompt)
        self.assertIn("Never merge", prompt)
        self.assertIn("non-empty diff", prompt)
        self.assertIn("duplicate/path/owner-conflict", prompt)


if __name__ == "__main__":
    unittest.main()
