from __future__ import annotations

import math
import unittest

from scripts.earnings_driver_bridge import (
    DriverModel,
    DriverModelValidationError,
    dependency_path,
    deterministic_driver_model_id,
    evaluate_driver_model,
)


class EarningsDriverBridgeTests(unittest.TestCase):
    def model(self) -> dict:
        return {
            "security_code": "6622",
            "target_fiscal_year": "FY2027",
            "version": "v1",
            "as_of": "2026-08-09",
            "status": "COMPLETE",
            "nodes": [
                {
                    "node_id": "base_volume",
                    "node_type": "ASSUMPTION",
                    "metric": "VOLUME",
                    "scope": "SEGMENT",
                    "scope_id": "material-processing",
                    "scenario": "BASE",
                    "value": 120,
                    "unit": "COUNT",
                    "target_fiscal_year": "FY2027",
                    "formula": None,
                    "source_refs": ["fact:orders"],
                    "assumption_text": "受注成長を踏まえ数量120をBase前提とする",
                    "as_of": "2026-08-09",
                    "confidence": "MEDIUM",
                },
                {
                    "node_id": "base_price",
                    "node_type": "ASSUMPTION",
                    "metric": "PRICE",
                    "scope": "SEGMENT",
                    "scope_id": "material-processing",
                    "scenario": "BASE",
                    "value": 1000000,
                    "unit": "JPY",
                    "target_fiscal_year": "FY2027",
                    "formula": None,
                    "source_refs": ["fact:price-proxy"],
                    "assumption_text": "単価100万円をBase前提とする",
                    "as_of": "2026-08-09",
                    "confidence": "LOW",
                },
                {
                    "node_id": "base_revenue",
                    "node_type": "DERIVED",
                    "metric": "REVENUE",
                    "scope": "SEGMENT",
                    "scope_id": "material-processing",
                    "scenario": "BASE",
                    "value": None,
                    "unit": "JPY",
                    "target_fiscal_year": "FY2027",
                    "formula": {"operation": "MULTIPLY", "input_refs": ["base_volume", "base_price"]},
                    "source_refs": [],
                    "assumption_text": None,
                    "as_of": "2026-08-09",
                    "confidence": "MEDIUM",
                },
                {
                    "node_id": "base_margin",
                    "node_type": "ASSUMPTION",
                    "metric": "MARGIN",
                    "scope": "SEGMENT",
                    "scope_id": "material-processing",
                    "scenario": "BASE",
                    "value": 10,
                    "unit": "%",
                    "target_fiscal_year": "FY2027",
                    "formula": None,
                    "source_refs": ["fact:margin"],
                    "assumption_text": "営業利益率10%をBase前提とする",
                    "as_of": "2026-08-09",
                    "confidence": "MEDIUM",
                },
                {
                    "node_id": "base_operating_profit",
                    "node_type": "DERIVED",
                    "metric": "OPERATING_PROFIT",
                    "scope": "SEGMENT",
                    "scope_id": "material-processing",
                    "scenario": "BASE",
                    "value": None,
                    "unit": "JPY",
                    "target_fiscal_year": "FY2027",
                    "formula": {"operation": "APPLY_MARGIN", "input_refs": ["base_revenue", "base_margin"]},
                    "source_refs": [],
                    "assumption_text": None,
                    "as_of": "2026-08-09",
                    "confidence": "MEDIUM",
                },
            ],
            "outputs": {
                "base": {"net_income_ref": None, "eps_ref": None}
            },
        }

    def test_deterministic_identity(self) -> None:
        first = DriverModel.from_mapping(self.model())
        second = DriverModel.from_mapping(self.model())
        self.assertEqual(first.driver_model_id, second.driver_model_id)
        self.assertEqual(
            first.driver_model_id,
            deterministic_driver_model_id(
                security_code="6622", target_fiscal_year="FY2027", version="v1"
            ),
        )

    def test_deterministic_evaluation_and_dependency_path(self) -> None:
        result = evaluate_driver_model(self.model())
        values = {node["node_id"]: node["value"] for node in result["nodes"]}
        self.assertEqual(values["base_revenue"], 120000000.0)
        self.assertEqual(values["base_operating_profit"], 12000000.0)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(
            dependency_path(self.model(), "base_operating_profit"),
            ["base_operating_profit", "base_revenue", "base_volume", "base_price", "base_margin"],
        )

    def test_missing_value_propagates_partial_not_zero(self) -> None:
        raw = self.model()
        raw["nodes"][0]["value"] = None
        result = evaluate_driver_model(raw)
        values = {node["node_id"]: node["value"] for node in result["nodes"]}
        self.assertIsNone(values["base_revenue"])
        self.assertIsNone(values["base_operating_profit"])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("MISSING_VALUE:base_volume", result["warnings"])

    def test_cycle_fails_closed(self) -> None:
        raw = self.model()
        raw["nodes"][2]["formula"]["input_refs"] = ["base_operating_profit", "base_price"]
        with self.assertRaisesRegex(DriverModelValidationError, "cyclic dependency"):
            DriverModel.from_mapping(raw)

    def test_fiscal_year_mismatch_fails_closed(self) -> None:
        raw = self.model()
        raw["nodes"][0]["target_fiscal_year"] = "FY2028"
        with self.assertRaisesRegex(DriverModelValidationError, "fiscal-year mismatch"):
            DriverModel.from_mapping(raw)

    def test_incompatible_add_units_fail_closed(self) -> None:
        raw = self.model()
        raw["nodes"][2]["formula"] = {"operation": "ADD", "input_refs": ["base_volume", "base_price"]}
        with self.assertRaisesRegex(DriverModelValidationError, "compatible units"):
            evaluate_driver_model(raw)

    def test_numeric_string_bool_nan_inf_are_rejected(self) -> None:
        for bad in ["120", True, math.nan, math.inf, -math.inf]:
            with self.subTest(bad=bad):
                raw = self.model()
                raw["nodes"][0]["value"] = bad
                with self.assertRaises(DriverModelValidationError):
                    DriverModel.from_mapping(raw)

    def test_zero_denominator_fails_closed(self) -> None:
        raw = self.model()
        raw["nodes"].extend(
            [
                {
                    "node_id": "net_income",
                    "node_type": "OBSERVED",
                    "metric": "NET_INCOME",
                    "scope": "COMPANY",
                    "scope_id": None,
                    "scenario": "BASE",
                    "value": 100,
                    "unit": "JPY",
                    "target_fiscal_year": "FY2027",
                    "formula": None,
                    "source_refs": ["fact:net-income"],
                    "assumption_text": None,
                    "as_of": "2026-08-09",
                    "confidence": "HIGH",
                },
                {
                    "node_id": "shares",
                    "node_type": "OBSERVED",
                    "metric": "SHARES",
                    "scope": "COMPANY",
                    "scope_id": None,
                    "scenario": "COMMON",
                    "value": 0,
                    "unit": "COUNT",
                    "target_fiscal_year": "FY2027",
                    "formula": None,
                    "source_refs": ["fact:shares"],
                    "assumption_text": None,
                    "as_of": "2026-08-09",
                    "confidence": "HIGH",
                },
                {
                    "node_id": "eps",
                    "node_type": "DERIVED",
                    "metric": "EPS",
                    "scope": "COMPANY",
                    "scope_id": None,
                    "scenario": "BASE",
                    "value": None,
                    "unit": "JPY",
                    "target_fiscal_year": "FY2027",
                    "formula": {"operation": "PER_SHARE", "input_refs": ["net_income", "shares"]},
                    "source_refs": [],
                    "assumption_text": None,
                    "as_of": "2026-08-09",
                    "confidence": "HIGH",
                },
            ]
        )
        raw["outputs"] = {"base": {"net_income_ref": "net_income", "eps_ref": "eps"}}
        with self.assertRaisesRegex(DriverModelValidationError, "share count cannot be zero"):
            evaluate_driver_model(raw)

    def test_assumption_cannot_be_silent(self) -> None:
        raw = self.model()
        raw["nodes"][0]["assumption_text"] = None
        with self.assertRaisesRegex(DriverModelValidationError, "requires assumption_text"):
            DriverModel.from_mapping(raw)

    def test_operating_profit_only_can_remain_partial(self) -> None:
        raw = self.model()
        raw["status"] = "PARTIAL"
        result = evaluate_driver_model(raw)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["outputs"]["base"]["net_income"])
        self.assertIsNone(result["outputs"]["base"]["eps"])


if __name__ == "__main__":
    unittest.main()
