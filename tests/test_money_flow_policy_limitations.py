from __future__ import annotations

import unittest

from scripts.money_flow_policy_limitations import has_retrospective_membership_history


THEME_ID = "theme:ai-data-center-power-infrastructure"
CONFIG = {
    "themes": [
        {
            "id": THEME_ID,
            "membership_as_of": "2026-08-09",
            "backfill_policy": "RETROSPECTIVE_MEMBERSHIP_IF_HISTORICAL_MEMBERSHIP_UNAVAILABLE",
        }
    ]
}


class MoneyFlowPolicyLimitationsTests(unittest.TestCase):
    def test_historical_row_before_membership_keeps_limitation(self):
        history = [{"kind": "THEME", "id": THEME_ID, "as_of": "2024-09-26"}]
        self.assertTrue(has_retrospective_membership_history(history, theme_config=CONFIG, theme_id=THEME_ID))

    def test_current_only_history_does_not_invent_limitation(self):
        history = [{"kind": "THEME", "id": THEME_ID, "as_of": "2026-08-09"}]
        self.assertFalse(has_retrospective_membership_history(history, theme_config=CONFIG, theme_id=THEME_ID))

    def test_policy_must_explicitly_authorize_retrospective_membership(self):
        config = {"themes": [{"id": THEME_ID, "membership_as_of": "2026-08-09"}]}
        history = [{"kind": "THEME", "id": THEME_ID, "as_of": "2024-09-26"}]
        self.assertFalse(has_retrospective_membership_history(history, theme_config=config, theme_id=THEME_ID))


if __name__ == "__main__":
    unittest.main()
