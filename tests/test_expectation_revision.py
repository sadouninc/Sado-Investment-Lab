from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.expectation_revision import (
    ExpectationContractError,
    append_snapshot,
    latest_revision_view,
    load_history,
    revision_delta,
    validate_snapshot,
)


def snapshot(*, as_of: str = "2026-08-01", value=300.0, expectation_type: str = "CONSENSUS", metric: str = "EPS", unit: str = "JPY", status: str = "OK"):
    return {
        "security_code": "7974",
        "target_fiscal_period": "FY2027",
        "as_of": as_of,
        "expectation_type": expectation_type,
        "metric": metric,
        "value": value,
        "unit": unit,
        "source_ref": "fixture://consensus",
        "source_authority": "SECONDARY" if expectation_type == "CONSENSUS" else "INTERNAL",
        "observed_at": f"{as_of}T09:00:00+09:00",
        "coverage": {"analyst_count": 10, "dispersion": None, "status": status},
        "provenance": {"fixture": True},
    }


class ExpectationRevisionTests(unittest.TestCase):
    def test_identity_is_deterministic_and_separates_source_types(self):
        first = validate_snapshot(snapshot())
        second = validate_snapshot(snapshot())
        sado = validate_snapshot(snapshot(expectation_type="SADO_SCENARIO"))
        self.assertEqual(first["expectation_id"], second["expectation_id"])
        self.assertNotEqual(first["expectation_id"], sado["expectation_id"])

    def test_append_is_idempotent_and_conflicting_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "expectations.jsonl"
            row = snapshot()
            self.assertEqual(append_snapshot(path, row), "INSERTED")
            self.assertEqual(append_snapshot(path, row), "UNCHANGED")
            conflict = snapshot(value=310.0)
            with self.assertRaises(ExpectationContractError):
                append_snapshot(path, conflict)
            self.assertEqual(len(load_history(path)), 1)

    def test_unavailable_is_not_zero_and_must_not_carry_value(self):
        unavailable = snapshot(value=None, status="UNAVAILABLE")
        validated = validate_snapshot(unavailable)
        self.assertIsNone(validated["value"])
        with self.assertRaises(ExpectationContractError):
            validate_snapshot(snapshot(value=0.0, status="UNAVAILABLE"))

    def test_available_snapshot_requires_value(self):
        with self.assertRaises(ExpectationContractError):
            validate_snapshot(snapshot(value=None, status="PARTIAL"))

    def test_revision_delta_requires_identical_basis(self):
        old = validate_snapshot(snapshot(as_of="2026-07-01", value=300))
        new = validate_snapshot(snapshot(as_of="2026-08-01", value=330))
        delta = revision_delta(old, new)
        self.assertEqual(delta["direction"], "UP")
        self.assertEqual(delta["pct"], 10.0)
        mismatched = validate_snapshot(snapshot(as_of="2026-08-01", value=330, unit="JPY_MN", metric="NET_INCOME"))
        with self.assertRaises(ExpectationContractError):
            revision_delta(old, mismatched)

    def test_revision_view_reports_mixed_and_no_fake_acceleration(self):
        rows = [
            validate_snapshot(snapshot(as_of="2026-06-01", value=280)),
            validate_snapshot(snapshot(as_of="2026-07-01", value=320)),
            validate_snapshot(snapshot(as_of="2026-08-01", value=310)),
        ]
        view = latest_revision_view(rows, template=rows[-1])
        self.assertEqual(view["direction"], "MIXED")
        self.assertIsNone(view["acceleration"])
        self.assertEqual(view["acceleration_status"], "NOT_IMPLEMENTED_V1")

    def test_consensus_company_guidance_and_sado_scenario_remain_separate_series(self):
        consensus = validate_snapshot(snapshot(value=340, expectation_type="CONSENSUS"))
        guidance = validate_snapshot(snapshot(value=330, expectation_type="COMPANY_GUIDANCE"))
        sado = validate_snapshot(snapshot(value=500, expectation_type="SADO_SCENARIO"))
        self.assertEqual(len({consensus["expectation_id"], guidance["expectation_id"], sado["expectation_id"]}), 3)


if __name__ == "__main__":
    unittest.main()
