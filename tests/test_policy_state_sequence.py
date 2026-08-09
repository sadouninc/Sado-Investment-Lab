from __future__ import annotations

import copy
import unittest

from scripts.policy_state_sequence import PolicyStateSequenceError, summarize_policy_state_sequence


def row(as_of: str, state: str, *, complete: str = "OK", missing_axis: bool = False) -> dict:
    scores = {
        "relative_strength": 60.0,
        "activity": 60.0,
        "breadth": 60.0,
        "heat": 60.0,
        "acceleration": 60.0,
    }
    if missing_axis:
        scores["acceleration"] = None
    return {
        "kind": "THEME",
        "id": "theme:test",
        "as_of": as_of,
        "state": state,
        "data_completeness": complete,
        "scores": scores,
    }


class PolicyStateSequenceTests(unittest.TestCase):
    def test_policy_leads_sequence(self):
        history = [row("2024-10-01", "COLD"), row("2024-10-04", "COLD"), row("2024-10-10", "WARMING"), row("2024-10-18", "INFLOW")]
        result = summarize_policy_state_sequence(history, policy_t0="2024-10-04", theme_id="theme:test")
        self.assertEqual(result["pre_policy_state"]["state"], "COLD")
        self.assertEqual(result["state_at_or_before_policy"]["as_of"], "2024-10-04")
        self.assertEqual(result["first_post_policy_warming"], "2024-10-10")
        self.assertEqual(result["first_post_policy_inflow"], "2024-10-18")
        self.assertFalse(result["post_policy_persistence"])
        self.assertFalse(result["post_policy_reacceleration"])

    def test_market_lead_persistence(self):
        history = [row("2024-09-20", "WARMING"), row("2024-10-03", "INFLOW"), row("2024-10-08", "INFLOW")]
        result = summarize_policy_state_sequence(history, policy_t0="2024-10-04", theme_id="theme:test")
        self.assertTrue(result["post_policy_persistence"])
        self.assertFalse(result["post_policy_reacceleration"])
        self.assertEqual(result["reliable_strongest_pre_policy_state"], "INFLOW")

    def test_reacceleration_requires_cooling_between_pre_signal_and_policy(self):
        history = [row("2024-09-20", "INFLOW"), row("2024-09-30", "COLD"), row("2024-10-03", "COLD"), row("2024-10-10", "WARMING"), row("2024-10-18", "INFLOW")]
        result = summarize_policy_state_sequence(history, policy_t0="2024-10-04", theme_id="theme:test")
        self.assertTrue(result["post_policy_persistence"])
        self.assertTrue(result["post_policy_reacceleration"])

    def test_partial_pre_policy_signal_is_not_reliable_persistence(self):
        history = [row("2024-09-26", "INFLOW", complete="PARTIAL", missing_axis=True), row("2024-10-03", "COLD", complete="PARTIAL", missing_axis=True), row("2024-11-06", "WARMING"), row("2024-11-08", "INFLOW")]
        result = summarize_policy_state_sequence(history, policy_t0="2024-10-04", theme_id="theme:test")
        self.assertEqual(result["strongest_pre_policy_state"], "INFLOW")
        self.assertIsNone(result["reliable_strongest_pre_policy_state"])
        self.assertFalse(result["post_policy_persistence"])
        self.assertFalse(result["post_policy_reacceleration"])
        self.assertEqual(result["reliable_first_post_policy_warming"], "2024-11-06")

    def test_ok_without_all_required_axes_is_not_reliable(self):
        history = [row("2024-10-10", "WARMING", missing_axis=True)]
        result = summarize_policy_state_sequence(history, policy_t0="2024-10-04", theme_id="theme:test")
        self.assertEqual(result["first_post_policy_warming"], "2024-10-10")
        self.assertIsNone(result["reliable_first_post_policy_warming"])

    def test_other_theme_is_ignored(self):
        history = [row("2024-10-10", "WARMING")]
        other = copy.deepcopy(history[0])
        other["id"] = "theme:other"
        other["as_of"] = "2024-10-05"
        result = summarize_policy_state_sequence([other, *history], policy_t0="2024-10-04", theme_id="theme:test")
        self.assertEqual(len(result["sequence"]), 1)

    def test_omitted_theme_id_accepts_single_canonical_identity(self):
        result = summarize_policy_state_sequence([row("2024-10-10", "WARMING")], policy_t0="2024-10-04")
        self.assertEqual(result["theme_id"], "theme:test")
        self.assertEqual(result["first_post_policy_warming"], "2024-10-10")

    def test_omitted_theme_id_rejects_cross_theme_persistence(self):
        pre = row("2024-10-01", "WARMING")
        post = row("2024-10-10", "INFLOW")
        post["id"] = "theme:other"
        with self.assertRaises(PolicyStateSequenceError):
            summarize_policy_state_sequence([pre, post], policy_t0="2024-10-04")

    def test_omitted_theme_id_rejects_cross_theme_same_state_different_dates(self):
        first = row("2024-10-01", "COLD")
        second = row("2024-10-10", "COLD")
        second["id"] = "theme:other"
        with self.assertRaises(PolicyStateSequenceError):
            summarize_policy_state_sequence([first, second], policy_t0="2024-10-04")

    def test_missing_or_blank_theme_identity_fails_closed(self):
        for invalid in (None, "", "   "):
            bad = row("2024-10-10", "WARMING")
            bad["id"] = invalid
            with self.subTest(invalid=invalid):
                with self.assertRaises(PolicyStateSequenceError):
                    summarize_policy_state_sequence([bad], policy_t0="2024-10-04")

    def test_same_day_same_state_but_different_theme_fails_closed_when_omitted(self):
        first = row("2024-10-10", "WARMING")
        second = copy.deepcopy(first)
        second["id"] = "theme:other"
        with self.assertRaises(PolicyStateSequenceError):
            summarize_policy_state_sequence([first, second], policy_t0="2024-10-04")

    def test_conflicting_same_day_fails_closed(self):
        with self.assertRaises(PolicyStateSequenceError):
            summarize_policy_state_sequence([row("2024-10-10", "WARMING"), row("2024-10-10", "INFLOW")], policy_t0="2024-10-04", theme_id="theme:test")

    def test_deterministic_and_non_mutating(self):
        history = [row("2024-10-10", "WARMING"), row("2024-10-18", "INFLOW")]
        original = copy.deepcopy(history)
        self.assertEqual(summarize_policy_state_sequence(history, policy_t0="2024-10-04", theme_id="theme:test"), summarize_policy_state_sequence(history, policy_t0="2024-10-04", theme_id="theme:test"))
        self.assertEqual(history, original)


if __name__ == "__main__":
    unittest.main()
