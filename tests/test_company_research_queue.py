import unittest

from scripts.company_research_queue import (
    ResearchQueueError,
    ResearchQueueRecord,
    ResearchQueueRegistry,
    complete_research,
    start_research,
)


class CompanyResearchQueueTests(unittest.TestCase):
    def _candidate(self, **overrides):
        payload = {
            "security_code": "7974",
            "company_name": "Nintendo Co., Ltd.",
            "candidate_sources": ["OWNER_PICK", "MONEY_FLOW"],
            "selection_reason": "Owner Pick Research Gap + discovery signal",
            "owner_pick": True,
            "candidate_as_of": "2026-08-09",
            "research_status": "NOT_STARTED",
            "research_gap": "HIGH",
            "money_flow_context": {"state": "WARMING"},
        }
        payload.update(overrides)
        return payload

    def test_candidate_handoff_enters_queued_and_preserves_provenance(self):
        record = ResearchQueueRecord.from_candidate_handoff(self._candidate())
        self.assertEqual(record.status, "QUEUED")
        self.assertEqual(record.security_code, "7974")
        self.assertEqual(record.candidate_sources, ("MONEY_FLOW", "OWNER_PICK"))
        self.assertEqual(record.money_flow_context["state"], "WARMING")

    def test_start_research_requires_explicit_command(self):
        record = ResearchQueueRecord.from_candidate_handoff(self._candidate())
        with self.assertRaises(ResearchQueueError):
            start_research(record, command="AUTO_START")
        started = start_research(record, command="START_RESEARCH")
        self.assertEqual(started.status, "IN_PROGRESS")
        self.assertEqual(start_research(started, command="START_RESEARCH"), started)

    def test_duplicate_enqueue_is_idempotent_and_conflict_fails_closed(self):
        registry = ResearchQueueRegistry()
        record = ResearchQueueRecord.from_candidate_handoff(self._candidate())
        self.assertEqual(registry.enqueue(record), "INSERTED")
        self.assertEqual(registry.enqueue(record), "UNCHANGED")
        conflicting = ResearchQueueRecord.from_candidate_handoff(
            self._candidate(selection_reason="retroactively changed reason")
        )
        with self.assertRaises(ResearchQueueError):
            registry.enqueue(conflicting)

    def test_completion_requires_in_progress_or_review(self):
        queued = ResearchQueueRecord.from_candidate_handoff(self._candidate())
        with self.assertRaises(ResearchQueueError):
            complete_research(queued, quality_gate_passed=True)
        started = start_research(queued, command="START_RESEARCH")
        self.assertEqual(complete_research(started, quality_gate_passed=False).status, "NEEDS_REVIEW")
        self.assertEqual(complete_research(started, quality_gate_passed=True).status, "CURRENT")


if __name__ == "__main__":
    unittest.main()
