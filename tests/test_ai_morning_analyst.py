from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ai_morning_analyst import SYSTEM_PROMPT, estimate_cost, extract_output_text, render_report


class AIMorningAnalystTest(unittest.TestCase):
    def test_extract_output_text(self) -> None:
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "# AI Morning Report\nOK"}],
                }
            ]
        }
        self.assertIn("# AI Morning Report", extract_output_text(payload))

    def test_render_report_preserves_dataset_quality(self) -> None:
        rendered = render_report(
            "# AI Morning Report\n## データ品質\nPARTIAL",
            {"as_of": "2026-08-07", "data_quality": {"status": "PARTIAL"}},
            "test-model",
        )
        self.assertIn("dataset_as_of: 2026-08-07", rendered)
        self.assertIn("dataset_status: PARTIAL", rendered)
        self.assertIn("model: test-model", rendered)

    def test_report_instructions_keep_unscored_historical_candidates_unverified(self) -> None:
        self.assertIn("今日の検証済み注目銘柄は未確定", SYSTEM_PROMPT)
        self.assertIn("total_priority", SYSTEM_PROMPT)
        self.assertIn("last_researched_at", SYSTEM_PROMPT)
        self.assertIn("historical portfolio holdings", SYSTEM_PROMPT)
        self.assertIn("candidate-specific source_status", SYSTEM_PROMPT)

    def test_estimated_cost_requires_explicit_pricing(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_INPUT_COST_PER_MILLION", None)
            os.environ.pop("OPENAI_OUTPUT_COST_PER_MILLION", None)
            cost, basis = estimate_cost({"input_tokens": 100, "output_tokens": 50})
        self.assertIsNone(cost)
        self.assertEqual("pricing_not_configured", basis)

    def test_estimated_cost_uses_repository_rates(self) -> None:
        with patch.dict(
            os.environ,
            {"OPENAI_INPUT_COST_PER_MILLION": "2", "OPENAI_OUTPUT_COST_PER_MILLION": "8"},
            clear=False,
        ):
            cost, basis = estimate_cost({"input_tokens": 1000, "output_tokens": 500})
        self.assertEqual(0.006, cost)
        self.assertEqual("estimated_from_repository_variables", basis)


if __name__ == "__main__":
    unittest.main()
