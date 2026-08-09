from __future__ import annotations

import unittest

from scripts.developing_signal_evaluation import evaluate_signals
from scripts.developing_signal_registry import transition_signal, validate_signal


BASE = {
    "signal_key": "ai-capex-roi-shift",
    "title": "AI投資評価軸の変化",
    "signal_type": "THEME",
    "status": "WATCHING",
    "direction": "UNKNOWN",
    "first_observed_at": "2026-08-01T10:00:00+09:00",
    "last_observed_at": "2026-08-01T10:00:00+09:00",
    "created_by": "ASAHI",
    "summary": "継続観測する。",
    "why_it_may_matter": "投資判断へ影響しうる。",
    "source_refs": ["source:a"],
    "related_entities": [{"type": "THEME", "id": "AI"}],
    "related_hypothesis_refs": [],
    "strengthening_conditions": [],
    "invalidation_conditions": [],
    "next_checkpoint": "2026-08-10T10:00:00+09:00",
    "expires_at": None,
    "promotion_target_candidates": ["THEME_RESEARCH"],
    "observations": [],
}


def make_signal(key: str, creator: str = "ASAHI"):
    raw = dict(BASE)
    raw["signal_key"] = key
    raw["created_by"] = creator
    return validate_signal(raw)


class DevelopingSignalEvaluationTests(unittest.TestCase):
    def test_empty_input_is_unknown_not_zero_quality(self):
        result = evaluate_signals([])
        self.assertEqual(result["signal_count"], 0)
        self.assertIsNone(result["rates"]["promotion_rate_pct"])
        self.assertEqual(result["sample_status"], "INSUFFICIENT")

    def test_rates_keep_active_separate_from_resolved(self):
        promoted = transition_signal(make_signal("a"), "PROMOTED", at="2026-08-03T10:00:00+09:00", promotion_ref="research:a")
        dismissed = transition_signal(make_signal("b"), "DISMISSED", at="2026-08-03T10:00:00+09:00", reason="反証")
        active = make_signal("c")
        result = evaluate_signals([promoted, dismissed, active])
        self.assertEqual(result["rates"]["promotion_rate_pct"], 33.33)
        self.assertEqual(result["rates"]["dismiss_rate_pct"], 33.33)
        self.assertEqual(result["rates"]["active_rate_pct"], 33.33)

    def test_promotion_lead_time_uses_first_observed(self):
        promoted = transition_signal(make_signal("lead"), "PROMOTED", at="2026-08-05T10:00:00+09:00", promotion_ref="research:lead")
        result = evaluate_signals([promoted])
        self.assertEqual(result["promotion_lead_time"]["median_days"], 4.0)

    def test_sensor_metrics_are_deterministic_and_sparse_guarded(self):
        a = transition_signal(make_signal("a1", "REI"), "PROMOTED", at="2026-08-02T10:00:00+09:00", promotion_ref="research:a1")
        b = make_signal("a2", "REI")
        c = make_signal("b1", "ASAHI")
        first = evaluate_signals([a, b, c])
        second = evaluate_signals([c, b, a])
        self.assertEqual(first, second)
        rei = next(x for x in first["sensor_metrics"] if x["sensor"] == "REI")
        self.assertEqual(rei["promotion_rate_pct"], 50.0)
        self.assertEqual(rei["sample_status"], "INSUFFICIENT")

    def test_invalid_signal_fails_closed(self):
        bad = make_signal("bad")
        bad["status"] = "PROMOTED"
        with self.assertRaises(ValueError):
            evaluate_signals([bad])


if __name__ == "__main__":
    unittest.main()
