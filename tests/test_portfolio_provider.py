from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import tempfile
import unittest

from scripts.morning_dataset.providers.portfolio import PortfolioProvider


class PortfolioProviderTest(unittest.TestCase):
    def write(self, root: Path, body: str) -> Path:
        path = root / "Current_Status.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_ok_when_fresh_and_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), """# Current Status\n> 最終更新: 2026-08-08\n\n## Portfolio\n> as_of: 2026-08-08\n- 日東紡（信用買い800株・信用売り100株）\n- 信越化学\n\n## Current Strategy\n- test\n""")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("2026-08-08", result.as_of)
            self.assertEqual("日東紡", result.data["positions"][0]["name"])
            self.assertEqual("信用買い800株・信用売り100株", result.data["positions"][0]["details"])
            self.assertIsNone(result.data["positions"][1]["details"])

    def test_stale_preserves_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), """# Current Status\n> 最終更新: 2026-08-08\n\n## Portfolio\n> as_of: 2026-08-04\n- ダイヘン\n""")
            result = PortfolioProvider(path, max_age_days=3, today=date(2026, 8, 8)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("ダイヘン", result.data["positions"][0]["name"])
            self.assertIn("4 days old", result.reason)

    def test_missing_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = PortfolioProvider(Path(tmp) / "missing.md", today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_missing_portfolio_section_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n> 最終更新: 2026-08-08\n\n## TODO\n- test\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("MISSING", result.status)

    def test_no_last_updated_is_partial_not_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n\n## Portfolio\n- GENDA\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIsNone(result.as_of)
            self.assertEqual("GENDA", result.data["positions"][0]["name"])

    def test_non_bullet_content_marks_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n> 最終更新: 2026-08-08\n\n## Portfolio\n> as_of: 2026-08-08\n- GENDA\nneeds-review\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(1, len(result.data["positions"]))

    def test_future_dated_markdown_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), """# Current Status
> 最終更新: 2026-08-08

## Portfolio
> as_of: 2026-08-09
- 信越化学
""")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("future", result.reason)
            self.assertEqual("信越化学", result.data["positions"][0]["name"])

    def test_future_dated_markdown_precedes_malformed_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), """# Current Status
> 最終更新: 2026-08-08

## Portfolio
> as_of: 2026-08-09
- 信越化学
needs-review
""")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("future", result.reason)
            self.assertEqual("信越化学", result.data["positions"][0]["name"])

    def test_future_dated_verified_json_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text(json.dumps({
                "as_of": "2026-08-09",
                "verification_status": "VERIFIED",
                "positions": [{
                    "security_code": "4063", "security_name": "信越化学",
                    "position_type": "cash", "quantity": 100,
                }],
            }, ensure_ascii=False), encoding="utf-8")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("future", result.reason)
            self.assertEqual(100, result.data["positions"][0]["quantity"])

    def test_canonical_verified_json_is_primary_machine_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text(json.dumps({
                "as_of": "2026-08-08",
                "verification_status": "VERIFIED",
                "base_snapshot": "verified-2026-08-08",
                "positions": [{
                    "security_code": "4063", "security_name": "信越化学",
                    "position_type": "cash", "quantity": 100,
                }],
            }, ensure_ascii=False), encoding="utf-8")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("VERIFIED", result.data["verification_status"])
            self.assertEqual("4063", result.data["positions"][0]["security_code"])

    def test_canonical_mismatch_is_partial_with_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text(json.dumps({
                "as_of": "2026-08-08",
                "verification_status": "MISMATCH",
                "positions": [{
                    "security_code": "4063", "security_name": "信越化学",
                    "position_type": "cash", "quantity": 100,
                }],
                "verification_diff": [{"security_code": "4063", "difference": 100}],
            }, ensure_ascii=False), encoding="utf-8")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertEqual(100, result.data["verification_diff"][0]["difference"])

    def test_canonical_invalid_date_is_partial_not_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text(json.dumps({
                "as_of": "unknown",
                "verification_status": "PROVISIONAL",
                "positions": [{
                    "security_code": "4063", "security_name": "信越化学",
                    "position_type": "cash", "quantity": 100,
                }],
            }, ensure_ascii=False), encoding="utf-8")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIn("YYYY-MM-DD", result.reason)


    def write_json(self, root: Path, payload) -> Path:
        path = root / "current.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    POSITION = {"security_code": "4063", "security_name": "信越化学", "position_type": "cash", "quantity": 100}

    def test_old_section_with_newer_global_update_stays_stale(self):
        # Mirrors Current_Status.md: Portfolio as_of 2026-08-08, file-wide 最終更新 2026-08-17.
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n> 最終更新: 2026-08-17\n\n## Portfolio\n\n> as_of: 2026-08-08\n- 日東紡績（信用買い900株）\n")
            result = PortfolioProvider(path, today=date(2026, 8, 17)).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("2026-08-08", result.as_of)
            self.assertIn("9 days old", result.reason)

    def test_global_update_alone_never_makes_portfolio_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n> 最終更新: 2026-08-08\n\n## Portfolio\n- 信越化学\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIsNone(result.as_of)
            self.assertIn("no explicit as_of", result.reason)
            self.assertIn("最終更新 is not used", result.reason)
            self.assertEqual("信越化学", result.data["positions"][0]["name"])

    def test_invalid_section_dates_are_partial_not_exception(self):
        for value in ("2026-13-45", "2026-02-30", "unknown", "", "2026-08-08garbage", "20260808"):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    path = self.write(Path(tmp), f"# Current Status\n\n## Portfolio\n> as_of: {value}\n- 信越化学\n")
                    result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.as_of)
                self.assertEqual("信越化学", result.data["positions"][0]["name"])

    def test_duplicate_section_dates_are_partial(self):
        for second in ("2026-08-08", "2026-08-01"):
            with self.subTest(second=second):
                with tempfile.TemporaryDirectory() as tmp:
                    path = self.write(Path(tmp), f"# Current Status\n\n## Portfolio\n> as_of: 2026-08-08\n> as_of: {second}\n- 信越化学\n")
                    result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.as_of)
                self.assertIn("2 as_of dates", result.reason)

    def test_date_in_other_section_is_not_portfolio_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n\n## Current Focus\n> as_of: 2026-08-08\n- ダイヘン\n\n## Portfolio\n- 信越化学\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
            self.assertEqual("PARTIAL", result.status)
            self.assertIsNone(result.as_of)

    def test_invalid_utf8_markdown_is_missing_not_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Current_Status.md"
            path.write_bytes("## Portfolio\n> as_of: 2026-08-08\n- ".encode("utf-8") + bytes([0xFF, 0xFE]) + b"\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIn("failed to read", result.reason)

    def test_empty_portfolio_section_is_not_zero_holdings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), "# Current Status\n\n## Portfolio\n> as_of: 2026-08-08\n\n## Next\n")
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
        self.assertEqual("MISSING", result.status)
        self.assertIsNone(result.data)
        self.assertIn("not evidence of zero holdings", result.reason)

    def test_non_object_json_is_missing_not_exception(self):
        for payload in ([self.POSITION], "VERIFIED", 3, None):
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as tmp:
                    result = PortfolioProvider(self.write_json(Path(tmp), payload), today=date(2026, 8, 8)).collect()
                self.assertEqual("MISSING", result.status)
                self.assertIn("must be an object", result.reason)

    def test_invalid_utf8_and_oversized_json_are_missing_not_exception(self):
        # 70 digits is below the interpreter's default int limit, so this also
        # checks that the explicit parse bound, not the runtime, decides.
        oversized = [b'{"as_of": "2026-08-08", "verification_status": "VERIFIED", "positions": [{"security_code": "4063", "quantity": '
                     + b"9" * digits + b"}]}" for digits in (70, 5000)]
        for raw in (b'{"as_of": "' + bytes([0xFF]) + b'"}', *oversized):
            with self.subTest(size=len(raw)):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "current.json"
                    path.write_bytes(raw)
                    result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
                self.assertEqual("MISSING", result.status)
                self.assertIn("invalid", result.reason)

    def test_unhashable_verification_status_is_partial_not_exception(self):
        for status in (["VERIFIED"], {"state": "VERIFIED"}, None, 1):
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as tmp:
                    path = self.write_json(Path(tmp), {"as_of": "2026-08-08", "verification_status": status, "positions": [self.POSITION]})
                    result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertIsNone(result.data["verification_status"])
                self.assertEqual(100, result.data["positions"][0]["quantity"])

    def test_empty_or_non_list_positions_are_not_zero_holdings(self):
        for positions in ([], {}, "none", None, ["4063"]):
            with self.subTest(positions=positions):
                with tempfile.TemporaryDirectory() as tmp:
                    path = self.write_json(Path(tmp), {"as_of": "2026-08-08", "verification_status": "VERIFIED", "positions": positions})
                    result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
                self.assertEqual("MISSING", result.status)
                self.assertIsNone(result.data)
                self.assertIn("not evidence of zero holdings", result.reason)

    def test_mixed_position_entries_keep_valid_rows_but_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(Path(tmp), {"as_of": "2026-08-08", "verification_status": "VERIFIED",
                                                "positions": [self.POSITION, "6622", None], "verification_diff": {"x": 1}})
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
        self.assertEqual("PARTIAL", result.status)
        self.assertEqual([self.POSITION], result.data["positions"])
        self.assertEqual([], result.data["verification_diff"])
        self.assertIn("2 position", result.reason)
        self.assertIn("verification_diff is not a list", result.reason)

    def test_json_non_text_or_malformed_as_of_is_partial(self):
        for as_of in (20260808, ["2026-08-08"], "2026-08-08garbage", "2026-02-30"):
            with self.subTest(as_of=as_of):
                with tempfile.TemporaryDirectory() as tmp:
                    path = self.write_json(Path(tmp), {"as_of": as_of, "verification_status": "VERIFIED", "positions": [self.POSITION]})
                    result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
                self.assertEqual("PARTIAL", result.status)
                self.assertTrue(result.as_of is None or isinstance(result.as_of, str))

    def test_verification_as_of_still_precedes_as_of(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(Path(tmp), {"as_of": "2026-08-01", "verification_as_of": "2026-08-08T09:00:00+09:00",
                                                "verification_status": "PROVISIONAL", "positions": [self.POSITION]})
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
        self.assertEqual("OK", result.status)
        self.assertEqual("2026-08-08T09:00:00+09:00", result.as_of)
        self.assertEqual("PROVISIONAL", result.data["verification_status"])

    def test_ordinary_integer_quantities_are_unchanged_by_parse_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(Path(tmp), {"as_of": "2026-08-08", "verification_status": "VERIFIED",
                                                "positions": [dict(self.POSITION, quantity=12345678901234567890)]})
            result = PortfolioProvider(path, today=date(2026, 8, 8)).collect()
        self.assertEqual("OK", result.status)
        self.assertEqual(12345678901234567890, result.data["positions"][0]["quantity"])

if __name__ == "__main__":
    unittest.main()
