from __future__ import annotations

from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/daily-knowledge-trigger.yml')


class DailyKnowledgeWorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding='utf-8')

    def test_manual_event_fixture_is_required_by_dispatch_schema(self) -> None:
        marker = 'event_fixture:\n        description: "Repository-relative JSON event fixture for manual validation"\n        required: true'
        self.assertIn(marker, self.text)

    def test_runtime_guard_matches_required_manual_fixture_contract(self) -> None:
        self.assertIn('workflow_dispatch requires event_fixture', self.text)
        self.assertIn('Event fixture not found:', self.text)

    def test_issue_label_trigger_is_preserved(self) -> None:
        self.assertIn('issues:\n    types: [labeled]', self.text)
        self.assertIn("github.event.label.name == 'daily-knowledge'", self.text)


if __name__ == '__main__':
    unittest.main()
