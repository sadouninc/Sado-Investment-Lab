from __future__ import annotations

import unittest

from scripts.developing_signal_registry import (
    append_observation,
    deterministic_signal_id,
    mark_possible_duplicate,
    transition_signal,
    validate_signal,
)


BASE = {
    "signal_key": "ai-capex-roi-shift",
    "title": "AI投資評価軸が需要量からROIへ移る兆候",
    "signal_type": "THEME",
    "status": "WATCHING",
    "direction": "UNKNOWN",
    "first_observed_at": "2026-08-09T10:00:00+09:00",
    "last_observed_at": "2026-08-09T10:00:00+09:00",
    "created_by": "ASAHI",
    "summary": "AI投資の評価軸変化を継続観測する。",
    "why_it_may_matter": "AIインフラ関連企業の評価軸と資金配分に影響しうる。",
    "source_refs": ["source:example"],
    "related_entities": [{"type": "THEME", "id": "AI_DATA_CENTER"}],
    "related_hypothesis_refs": [],
    "strengthening_conditions": ["ROI言及が複数社へ拡大"],
    "invalidation_conditions": ["需要量優先へ回帰"],
    "next_checkpoint": "2026-08-12T10:00:00+09:00",
    "expires_at": None,
    "promotion_target_candidates": ["THEME_RESEARCH", "CANDIDATE_SIGNAL"],
    "observations": [],
}


class DevelopingSignalRegistryTests(unittest.TestCase):
    def test_identity_is_deterministic_and_title_independent(self):
        first = deterministic_signal_id(BASE["signal_key"], BASE["first_observed_at"], BASE["related_entities"])
        second = deterministic_signal_id(BASE["signal_key"], BASE["first_observed_at"], BASE["related_entities"])
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("signal:ai-capex-roi-shift:2026-08-09:"))

    def test_validation_populates_identity(self):
        signal = validate_signal(dict(BASE))
        self.assertEqual(signal["status"], "WATCHING")
        self.assertEqual(signal["duplicate_state"], "UNIQUE")
        self.assertIn("signal_id", signal)

    def test_checkpoint_or_expiry_requires_reason_when_both_unknown(self):
        signal = dict(BASE, next_checkpoint=None, expires_at=None)
        with self.assertRaisesRegex(ValueError, "checkpoint_reason"):
            validate_signal(signal)
        validated = validate_signal(dict(signal, checkpoint_reason="決算日未確定のため日付は推測しない"))
        self.assertEqual(validated["checkpoint_reason"], "決算日未確定のため日付は推測しない")

    def test_append_observation_is_chronological_and_preserves_fact_interpretation_boundary(self):
        signal = validate_signal(dict(BASE))
        updated = append_observation(signal, {
            "observed_at": "2026-08-10T09:00:00+09:00",
            "source_ref": "source:second",
            "observation": "別企業もROIを投資判断指標として明示した。",
            "interpretation": "評価軸変化が広がる可能性。",
            "effect": "STRENGTHENS",
            "actor": "REI",
        })
        self.assertEqual(updated["last_observed_at"], "2026-08-10T09:00:00+09:00")
        self.assertEqual(updated["observations"][0]["effect"], "STRENGTHENS")
        self.assertIn("interpretation", updated["observations"][0])
        with self.assertRaisesRegex(ValueError, "append-only chronological"):
            append_observation(updated, {
                "observed_at": "2026-08-09T11:00:00+09:00",
                "source_ref": None,
                "observation": "過去時刻の追記",
                "effect": "NEUTRAL",
                "actor": "ASAHI",
            })

    def test_missing_source_is_unknown_not_negative(self):
        signal = validate_signal(dict(BASE, source_refs=[None]))
        self.assertEqual(signal["status"], "WATCHING")
        updated = append_observation(signal, {
            "observed_at": "2026-08-10T09:00:00+09:00",
            "source_ref": None,
            "observation": "一次ソース取得不可。事実確認は保留。",
            "effect": "NEUTRAL",
            "actor": "ASAHI",
        })
        self.assertEqual(updated["observations"][0]["effect"], "NEUTRAL")

    def test_promotion_requires_destination_and_terminal_timestamp(self):
        signal = validate_signal(dict(BASE))
        with self.assertRaisesRegex(ValueError, "promotion_ref"):
            transition_signal(signal, "PROMOTED", at="2026-08-11T10:00:00+09:00")
        promoted = transition_signal(signal, "PROMOTED", at="2026-08-11T10:00:00+09:00", promotion_ref="theme-research:ai-data-center")
        self.assertEqual(promoted["promotion_ref"], "theme-research:ai-data-center")
        self.assertEqual(promoted["promoted_at"], promoted["resolved_at"])
        with self.assertRaisesRegex(ValueError, "terminal signal"):
            append_observation(promoted, {
                "observed_at": "2026-08-12T10:00:00+09:00",
                "source_ref": "source:x",
                "observation": "terminal後の追記",
                "effect": "NEUTRAL",
                "actor": "REI",
            })

    def test_dismiss_and_supersede_require_reason_or_ref(self):
        signal = validate_signal(dict(BASE))
        with self.assertRaisesRegex(ValueError, "reason"):
            transition_signal(signal, "DISMISSED", at="2026-08-11T10:00:00+09:00")
        dismissed = transition_signal(signal, "DISMISSED", at="2026-08-11T10:00:00+09:00", reason="反証確認")
        self.assertEqual(dismissed["resolution_reason"], "反証確認")
        with self.assertRaisesRegex(ValueError, "superseded_by"):
            transition_signal(signal, "SUPERSEDED", at="2026-08-11T10:00:00+09:00", reason="統合")

    def test_terminal_transitions_cannot_predate_last_observation(self):
        signal = validate_signal(dict(BASE))
        cases = (
            ("PROMOTED", {"promotion_ref": "research:signal"}),
            ("DISMISSED", {"reason": "dismissed"}),
            ("EXPIRED", {"reason": "expired"}),
            ("SUPERSEDED", {"reason": "superseded", "superseded_by": "signal:replacement"}),
        )
        for status, kwargs in cases:
            with self.subTest(status=status), self.assertRaisesRegex(
                ValueError, "cannot precede last_observed_at"
            ):
                transition_signal(signal, status, at="2025-01-01T00:00:00+09:00", **kwargs)

    def test_transition_allows_same_instant_with_different_timezone_offset(self):
        signal = validate_signal(dict(BASE))
        promoted = transition_signal(
            signal,
            "PROMOTED",
            at="2026-08-09T01:00:00+00:00",
            promotion_ref="research:same-instant",
        )
        self.assertEqual(promoted["status"], "PROMOTED")

    def test_possible_duplicate_is_flagged_not_merged(self):
        signal = validate_signal(dict(BASE))
        flagged = mark_possible_duplicate(signal, ["signal:other:2026-08-09:abc"])
        self.assertEqual(flagged["duplicate_state"], "POSSIBLE_DUPLICATE")
        self.assertEqual(flagged["possible_duplicate_refs"], ["signal:other:2026-08-09:abc"])
        self.assertEqual(flagged["signal_id"], signal["signal_id"])


if __name__ == "__main__":
    unittest.main()
