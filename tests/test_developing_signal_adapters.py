from __future__ import annotations

import unittest

from scripts.developing_signal_adapters import (
    DevelopingSignalAdapterError,
    adapt_asahi_watch,
    adapt_money_flow,
    adapt_policy_cross_domain,
    adapt_rei_watch,
    adapt_team_signal,
)


BASE = {
    "signal_key": "ai-capex-roi-shift",
    "title": "AI投資評価軸が需要量からROIへ移る兆候",
    "signal_type": "THEME",
    "observed_at": "2026-08-09T13:00:00+09:00",
    "summary": "継続観測する価値がある初期兆候。",
    "why_it_may_matter": "AIインフラ関連企業の評価軸に影響しうる。",
    "source_refs": ["source:example"],
    "related_entities": [{"type": "THEME", "id": "AI_DATA_CENTER"}],
    "next_checkpoint": "2026-08-12T13:00:00+09:00",
}


class DevelopingSignalAdapterTests(unittest.TestCase):
    def test_asahi_requires_explicit_multi_day_follow_up(self):
        with self.assertRaisesRegex(DevelopingSignalAdapterError, "follow_up_required"):
            adapt_asahi_watch(dict(BASE))
        signal = adapt_asahi_watch(dict(BASE, follow_up_required=True))
        self.assertEqual(signal["created_by"], "ASAHI")
        self.assertEqual(signal["status"], "WATCHING")
        self.assertEqual(signal["adapter_metadata"]["decision_scope"], "WATCH_ONLY")
        self.assertIsNone(signal["adapter_metadata"]["trade_action"])

    def test_rei_requires_strategy_change_candidate_and_forces_key_person_type(self):
        with self.assertRaisesRegex(DevelopingSignalAdapterError, "strategic_change_candidate"):
            adapt_rei_watch(dict(BASE))
        signal = adapt_rei_watch(dict(BASE, strategic_change_candidate=True))
        self.assertEqual(signal["created_by"], "REI")
        self.assertEqual(signal["signal_type"], "KEY_PERSON")

    def test_policy_requires_cross_domain_and_keeps_raw_log_by_reference_only(self):
        payload = dict(BASE, policy_raw_ref="policy-raw:2026-08-09:001")
        with self.assertRaisesRegex(DevelopingSignalAdapterError, "cross_domain"):
            adapt_policy_cross_domain(payload)
        signal = adapt_policy_cross_domain(dict(payload, cross_domain=True))
        self.assertEqual(signal["created_by"], "POLICY")
        self.assertEqual(signal["signal_type"], "POLICY")
        self.assertEqual(signal["adapter_metadata"]["policy_raw_ref"], "policy-raw:2026-08-09:001")
        self.assertFalse(signal["adapter_metadata"]["raw_payload_copied"])

    def test_money_flow_accepts_only_warming_or_inflow_selection_window(self):
        payload = dict(
            BASE,
            money_flow_state="WARMING",
            selection_signal=True,
            flow_score=68.2,
            signal_type="THEME",
        )
        signal = adapt_money_flow(payload)
        self.assertEqual(signal["created_by"], "MONEY_FLOW")
        self.assertEqual(signal["adapter_metadata"]["money_flow_state"], "WARMING")
        self.assertEqual(signal["adapter_metadata"]["flow_score"], 68.2)
        for state in ("COLD", "HOT", "OVERHEATED"):
            with self.assertRaisesRegex(DevelopingSignalAdapterError, "WARMING or INFLOW"):
                adapt_money_flow(dict(payload, money_flow_state=state))
        with self.assertRaisesRegex(DevelopingSignalAdapterError, "selection_signal"):
            adapt_money_flow(dict(payload, selection_signal=False))

    def test_missing_source_stays_unknown_not_negative(self):
        signal = adapt_asahi_watch(dict(BASE, follow_up_required=True, source_refs=[None]))
        self.assertEqual(signal["source_refs"], [None])
        self.assertEqual(signal["status"], "WATCHING")
        self.assertEqual(signal["direction"], "UNKNOWN")

    def test_watch_never_triggers_trade_or_daily_review_by_itself(self):
        adapters = [
            ("ASAHI", dict(BASE, follow_up_required=True)),
            ("REI", dict(BASE, strategic_change_candidate=True)),
            ("POLICY", dict(BASE, cross_domain=True, policy_raw_ref="policy:1")),
            ("MONEY_FLOW", dict(BASE, money_flow_state="INFLOW", selection_signal=True, signal_type="THEME")),
        ]
        for sensor, payload in adapters:
            signal = adapt_team_signal(sensor, payload)
            self.assertEqual(signal["adapter_metadata"]["decision_scope"], "WATCH_ONLY")
            self.assertIsNone(signal["adapter_metadata"]["trade_action"])
            self.assertFalse(signal["adapter_metadata"]["daily_review_trigger"])

    def test_checkpoint_reason_is_still_enforced_by_canonical_contract(self):
        payload = dict(BASE, follow_up_required=True, next_checkpoint=None, expires_at=None)
        with self.assertRaisesRegex(ValueError, "checkpoint_reason"):
            adapt_asahi_watch(payload)
        signal = adapt_asahi_watch(dict(payload, checkpoint_reason="次の一次情報公開日が未確定"))
        self.assertEqual(signal["checkpoint_reason"], "次の一次情報公開日が未確定")

    def test_dispatch_rejects_unknown_sensor(self):
        with self.assertRaisesRegex(DevelopingSignalAdapterError, "unsupported sensor"):
            adapt_team_signal("UNKNOWN", dict(BASE))


if __name__ == "__main__":
    unittest.main()
