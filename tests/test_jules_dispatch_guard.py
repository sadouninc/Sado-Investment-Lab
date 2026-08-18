import unittest

from scripts.jules_dispatch_guard import DispatchControl, build_prompt, decide, parse_control


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


if __name__ == "__main__":
    unittest.main()
