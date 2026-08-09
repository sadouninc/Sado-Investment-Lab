import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.throughput_ledger import append_record, summarize


def record(**overrides):
    value = {
        "actor": "SORA",
        "run_at": "2026-08-10T03:41:15+09:00",
        "advanced_items": ["issue:69", "issue:298"],
        "prs_opened": 1,
        "issues_created": 0,
        "issues_refined": 0,
        "reviews_completed": 1,
        "blocked_items": 1,
        "wait_reused": True,
        "wait_reuse_work": ["issue:298"],
        "handoff_ready": ["issue:69"],
        "next_queue": ["issue:298"],
        "quality_gate": "PENDING",
    }
    value.update(overrides)
    return value


class ThroughputLedgerTest(unittest.TestCase):
    def test_append_is_idempotent_for_same_payload(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            self.assertEqual("APPENDED", append_record(path, record()))
            self.assertEqual("UNCHANGED", append_record(path, record()))
            self.assertEqual(1, len(path.read_text().splitlines()))

    def test_same_identity_different_payload_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            append_record(path, record())
            with self.assertRaises(ValueError):
                append_record(path, record(prs_opened=2))

    def test_no_wait_accepts_not_applicable(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            self.assertEqual(
                "APPENDED",
                append_record(path, record(wait_reused=False, wait_reuse_work=[], wait_not_reused_reason="NOT_APPLICABLE")),
            )
            summary = summarize(path)
            self.assertEqual(0, summary["wait_eligible_runs"])

    def test_wait_not_reused_requires_operational_reason(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            with self.assertRaises(ValueError):
                append_record(path, record(wait_reused=False, wait_reuse_work=[]))
            self.assertEqual(
                "APPENDED",
                append_record(path, record(wait_reused=False, wait_reuse_work=[], wait_not_reused_reason="OWNER_WAIT")),
            )
            summary = summarize(path)
            self.assertEqual(1, summary["wait_eligible_runs"])

    def test_wait_reused_requires_work_and_no_nonreuse_reason(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            with self.assertRaises(ValueError):
                append_record(path, record(wait_reused=True, wait_reuse_work=[]))
            with self.assertRaises(ValueError):
                append_record(path, record(wait_reused=True, wait_not_reused_reason="BLOCKED"))

    def test_summary_counts_non_pr_progress(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            append_record(path, record(prs_opened=0, issues_refined=1, advanced_items=["issue:298"]))
            summary = summarize(path)
            self.assertEqual(1, summary["runs"])
            self.assertEqual(1, summary["advanced_items"])
            self.assertEqual(0, summary["prs_opened"])
            self.assertEqual(1, summary["issues_refined"])
            self.assertEqual(1, summary["wait_reused_runs"])
            self.assertEqual(1, summary["wait_eligible_runs"])
            self.assertEqual(1, summary["quality_gate_counts"]["PENDING"])


if __name__ == "__main__":
    unittest.main()
