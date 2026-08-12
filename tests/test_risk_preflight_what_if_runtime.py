from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_risk_preflight_what_if import (
    attach_runtime_telemetry,
    build_runtime_result,
    write_outputs,
)


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
                request_id="req-buy-6622-001",
            )
        self.assertEqual("CALCULATED", result["state"])
        self.assertTrue(result["ephemeral"])
        self.assertFalse(result["is_order"])
        self.assertEqual([], result["canonical_mutations"])
        self.assertEqual(2_000_000, result["risk_preflight"]["after_if_executed"]["position_notional"])
        self.assertEqual("req-buy-6622-001", result["runtime"]["request_id"])

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
                request_id="req-sell-6622-001",
            )
        self.assertEqual("NOT_JUDGABLE", result["state"])
        self.assertIsNone(result["risk_preflight"])
        self.assertFalse(result["is_order"])
        self.assertEqual([], result["canonical_mutations"])
        self.assertEqual("req-sell-6622-001", result["runtime"]["request_id"])

    def test_runtime_identity_binds_github_run_without_changing_canonical_result(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "GITHUB_RUN_ID": "31599999999",
                "GITHUB_RUN_ATTEMPT": "2",
                "GITHUB_WORKFLOW": "Risk Preflight What-if",
            },
            clear=False,
        ):
            root = Path(tmp)
            result = build_runtime_result(
                security_code="6622",
                action="BUY",
                quantity=100,
                price=10000,
                account_type="MARGIN",
                portfolio_path=self._portfolio_file(root),
                captured_at="2026-08-12T22:30:00+09:00",
                request_id="req-identity-001",
            )
        self.assertEqual(
            {
                "request_id": "req-identity-001",
                "github_run_id": "31599999999",
                "github_run_attempt": "2",
                "workflow": "Risk Preflight What-if",
                "captured_at": "2026-08-12T22:30:00+09:00",
            },
            result["runtime"],
        )
        self.assertEqual([], result["canonical_mutations"])

    def test_missing_request_id_generates_nonempty_ephemeral_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = build_runtime_result(
                security_code="6622",
                action="BUY",
                quantity=100,
                price=10000,
                account_type="MARGIN",
                portfolio_path=self._portfolio_file(root),
                captured_at="2026-08-12T22:30:00+09:00",
            )
        self.assertTrue(result["runtime"]["request_id"].startswith("whatif-"))

    def test_result_artifact_is_json_and_does_not_create_canonical_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            result = {
                "state": "SOURCE_UNAVAILABLE",
                "ephemeral": True,
                "is_order": False,
                "canonical_mutations": [],
                "runtime": {"request_id": "req-artifact-001"},
            }
            write_outputs(result, output_path=output)
            loaded = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result, loaded)

    def test_runtime_telemetry_is_ops_only_and_keeps_run_identity(self):
        base = {
            "state": "CALCULATED",
            "ephemeral": True,
            "is_order": False,
            "canonical_mutations": [],
            "runtime": {"request_id": "req-telemetry-001"},
        }
        result = attach_runtime_telemetry(
            base,
            calculation_started_at="2026-08-12T21:40:00.000+09:00",
            calculation_completed_at="2026-08-12T21:40:00.125+09:00",
            calculation_duration_ms=125.1236,
            github_run_id="123456",
            github_run_attempt="2",
        )
        self.assertEqual(base, {
            "state": "CALCULATED",
            "ephemeral": True,
            "is_order": False,
            "canonical_mutations": [],
            "runtime": {"request_id": "req-telemetry-001"},
        })
        telemetry = result["runtime_telemetry"]
        self.assertEqual("OPS_DIAGNOSTICS_ONLY", telemetry["scope"])
        self.assertFalse(telemetry["canonical_mutation"])
        self.assertEqual("2026-08-12T21:40:00.125+09:00", telemetry["calculation_completed_at"])
        self.assertNotIn("result_ready_at", telemetry)
        self.assertEqual("123456", telemetry["github_run_id"])
        self.assertEqual("2", telemetry["github_run_attempt"])
        self.assertEqual(125.124, telemetry["calculation_duration_ms"])
        self.assertEqual("req-telemetry-001", result["runtime"]["request_id"])

    def test_missing_github_metadata_stays_unknown_not_fabricated(self):
        result = attach_runtime_telemetry(
            {"state": "INVALID_INPUT", "ephemeral": True, "runtime": {"request_id": "req-unknown-001"}},
            calculation_started_at="2026-08-12T21:40:00.000+09:00",
            calculation_completed_at="2026-08-12T21:40:00.001+09:00",
            calculation_duration_ms=1.0,
        )
        self.assertIsNone(result["runtime_telemetry"]["github_run_id"])
        self.assertIsNone(result["runtime_telemetry"]["github_run_attempt"])
        self.assertNotIn("result_ready_at", result["runtime_telemetry"])
        self.assertEqual("req-unknown-001", result["runtime"]["request_id"])


if __name__ == "__main__":
    unittest.main()
