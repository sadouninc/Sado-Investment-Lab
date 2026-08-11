from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from scripts.morning_dataset.providers.candidate_selector import CandidateSelectorProvider


class CandidateSelectorProviderTest(unittest.TestCase):
    def write_snapshot(self, root: str, payload: dict) -> Path:
        path = Path(root) / "candidate-selector.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reads_fresh_resolved_candidates_without_reranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-11",
                "ranked_candidates": [
                    {
                        "security_code": "6232",
                        "company_name": "ACSL",
                        "research_status": "NOT_STARTED",
                        "total_priority": 72.5,
                        "owner_pick": True,
                        "candidate_sources": ["OWNER_PICK"],
                        "selection_reason": "Owner Pick",
                        "last_researched_at": None,
                    }
                ],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual("6232", result.data[0]["security_code"])
            self.assertEqual(72.5, result.data[0]["total_priority"])
            self.assertTrue(result.data[0]["owner_pick"])

    def test_unresolved_candidate_is_not_assigned_a_guessed_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-11",
                "ranked_candidates": [
                    {"security_code": None, "company_name": "原子力", "research_status": "NOT_STARTED"},
                    {"security_code": "6232", "company_name": "ACSL", "research_status": "NOT_STARTED"},
                ],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11)).collect()
            self.assertEqual("OK", result.status)
            self.assertEqual(["6232"], [row["security_code"] for row in result.data])

    def test_only_unresolved_candidates_are_missing_not_fabricated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-11",
                "ranked_candidates": [{"security_code": None, "company_name": "送電網"}],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11)).collect()
            self.assertEqual("MISSING", result.status)
            self.assertIsNone(result.data)

    def test_stale_snapshot_preserves_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_snapshot(tmp, {
                "as_of": "2026-08-01",
                "ranked_candidates": [{"security_code": "6232", "company_name": "ACSL"}],
            })
            result = CandidateSelectorProvider(path, today=date(2026, 8, 11), max_age_days=3).collect()
            self.assertEqual("STALE", result.status)
            self.assertEqual("6232", result.data[0]["security_code"])

    def test_missing_snapshot_is_missing(self):
        result = CandidateSelectorProvider(Path("/missing/candidate-selector.json")).collect()
        self.assertEqual("MISSING", result.status)


if __name__ == "__main__":
    unittest.main()
