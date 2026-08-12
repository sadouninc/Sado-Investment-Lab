from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_risk_preflight_what_if import build_runtime_result, write_outputs


PORTFOLIO = {
    "schema_version": 1,
    "as_of": "2026-08-08",
    "verification_status": "VERIFIED",
    "base_snapshot": "verified-test",
    "authority": "test",
    "positions": [
        {
            "security_code": "6622",
            "security_name": "ダイヘン",
            "position_type": "margin_long",
            "quantity": 100,
        }
    ],
}


class RiskPreflightWhatIfRuntimeTests(unittest.TestCase):
    def _portfolio_file(self, root: Path) -> Path:
        path = root / "portfolio.json"
        path.write_text(json.dumps(PORTFOLIO, ensure_ascii=False), encoding="utf-8")
        return path

    def test_runtime_buy_is_ephemeral_and_uses_existing_calculator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = build_runtime_result(
                security_code="6622",
                action="BUY",
                quantity=100,
                price=10000,
                account_type="MARGIN",
                portfolio_path=self._portfolio_file(root),
                portfolio_equity=3_000_000,
                cash_available=1_500_000,
                captured_at="2026-08-12T20:30:00+09:00",
            )
        self.assertEqual("CALCULATED", result["state"])
        self.assertTrue(result["ephemeral"])
        self.assertFalse(result["is_order"])
        self.assertEqual([], result["canonical_mutations"])
        self.assertEqual(2_000_000, result["risk_preflight"]["after_if_executed"]["position_notional"])

    def test_expected_domain_error_is_returned_as_result_not_fabricated_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = build_runtime_result(
                security_code="6622",
                action="SELL",
                quantity=200,
                price=10000,
                account_type="MARGIN",
                portfolio_path=self._portfolio_file(root),
                captured_at="2026-08-12T20:30:00+09:00",
            )
        self.assertEqual("NOT_JUDGABLE", result["state"])
        self.assertIsNone(result["risk_preflight"])
        self.assertFalse(result["is_order"])
        self.assertEqual([], result["canonical_mutations"])

    def test_result_artifact_is_json_and_does_not_create_canonical_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            result = {
                "state": "SOURCE_UNAVAILABLE",
                "ephemeral": True,
                "is_order": False,
                "canonical_mutations": [],
            }
            write_outputs(result, output_path=output)
            loaded = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result, loaded)


if __name__ == "__main__":
    unittest.main()
