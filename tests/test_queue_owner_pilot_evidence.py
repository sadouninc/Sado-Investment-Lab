"""Regression coverage for #943 sanitized read-only Actions evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

from scripts.queue_owner_inventory_pilot import inspect_one_candidate

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/queue-owner-inventory-readonly-pilot.yml"


class PilotEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        step = self.workflow.split("- name: Preserve sanitized run evidence and summary", 1)
        self.assertEqual(2, len(step), "evidence step missing")
        start = step[1].split("python3 - <<'PY'\n", 1)
        self.assertEqual(2, len(start), "heredoc start missing")
        end = start[1].split("\n          PY\n", 1)
        self.assertEqual(2, len(end), "heredoc terminator missing")
        self.source = textwrap.dedent(end[0])

    def run_evidence(self, outcome, raw=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input.json"
            target = root / "result.json"
            if raw is not None:
                source.write_text(json.dumps(raw), encoding="utf-8")
            code = self.source.replace("/tmp/owner-pilot-result.json", str(source)).replace(
                "/tmp/owner-pilot-evidence/result.json", str(target))
            env = {"DIAGNOSTIC_OUTCOME": outcome, "GITHUB_RUN_ID": "123",
                   "GITHUB_RUN_ATTEMPT": "2", "GITHUB_EVENT_NAME": "schedule",
                   "GITHUB_SHA": "a" * 40}
            subprocess.run([sys.executable, "-c", code], env=env, check=True,
                           capture_output=True, text=True)
            return json.loads(target.read_text(encoding="utf-8"))

    def valid(self):
        return {"status": "HOLD", "reason": "OWNER_ISSUER_UNVERIFIED",
                "dispatch_allowed": False, "selected_issue": 100,
                "candidate_count": 1, "conflicting_prs": [],
                "raw_issue_body": "must-not-leak", "token": "must-not-leak"}

    def test_valid_diagnostic_and_metadata_are_preserved_without_raw_fields(self):
        evidence = self.run_evidence("success", self.valid())
        self.assertEqual("123", evidence["run_id"])
        self.assertEqual("2", evidence["run_attempt"])
        self.assertEqual("a" * 40, evidence["head_sha"])
        self.assertEqual("OWNER_ISSUER_UNVERIFIED", evidence["result"]["reason"])
        self.assertEqual(1, evidence["result"]["candidate_count"])
        self.assertNotIn("must-not-leak", json.dumps(evidence))
        self.assertIs(evidence["result"]["dispatch_allowed"], False)

    def test_verified_zero_is_distinct_from_unknown(self):
        raw = dict(self.valid(), reason="NO_READY_CANDIDATE", candidate_count=0,
                   selected_issue=None)
        result = self.run_evidence("success", raw)["result"]
        self.assertEqual("NO_READY_CANDIDATE", result["reason"])
        self.assertEqual(0, result["candidate_count"])
        self.assertIs(result["dispatch_allowed"], False)

    def test_actual_producer_unavailable_inputs_are_not_verified_zero(self):
        inventory = {"complete": True, "prs": []}
        malformed = inspect_one_candidate({"unexpected": []}, inventory)
        self.assertEqual("ISSUE_INVENTORY_INCOMPLETE", malformed["reason"])
        self.assertEqual(0, malformed["candidate_count"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            issues = root / "invalid.json"
            issues.write_text("{", encoding="utf-8")
            prs = root / "prs.json"
            prs.write_text(json.dumps(inventory), encoding="utf-8")
            output = root / "producer.json"
            subprocess.run(
                [sys.executable, "-m", "scripts.queue_owner_inventory_pilot",
                 "--issues", str(issues), "--open-prs", str(prs), "--output", str(output)],
                cwd=WORKFLOW.parents[2], env={}, check=True, capture_output=True, text=True)
            unavailable = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("INPUT_UNAVAILABLE", unavailable["reason"])
        for raw in (malformed, unavailable):
            with self.subTest(reason=raw["reason"]):
                result = self.run_evidence("success", raw)["result"]
                self.assertEqual(raw["reason"], result["reason"])
                for field in ("candidate_count", "selected_issue", "conflicting_prs"):
                    self.assertIsNone(result[field])
                self.assertIs(result["dispatch_allowed"], False)
        verified = inspect_one_candidate([], inventory)
        result = self.run_evidence("success", verified)["result"]
        self.assertEqual("NO_READY_CANDIDATE", result["reason"])
        self.assertEqual(0, result["candidate_count"])

    def test_incomplete_path_inventory_does_not_claim_no_conflicts(self):
        raw = inspect_one_candidate(
            [{"number": 100, "allowed_paths": ["scripts/a.py"], "owner_slice": "test"}],
            {"complete": False, "prs": []})
        result = self.run_evidence("success", raw)["result"]
        self.assertEqual("PR_PATH_INVENTORY_INCOMPLETE", result["reason"])
        self.assertEqual(1, result["candidate_count"])
        self.assertEqual(100, result["selected_issue"])
        self.assertIsNone(result["conflicting_prs"])

    def test_inconsistent_or_out_of_bound_counts_are_rejected(self):
        for raw in (dict(self.valid(), candidate_count=2),
                    dict(self.valid(), candidate_count=0),
                    dict(self.valid(), reason="NO_READY_CANDIDATE"),
                    dict(self.valid(), reason="PR_PATH_CONFLICT")):
            with self.subTest(raw=raw):
                result = self.run_evidence("success", raw)["result"]
                self.assertEqual("DIAGNOSTIC_OUTPUT_INVALID_OR_MISSING", result["reason"])
                self.assertIsNone(result["candidate_count"])

    def test_missing_required_fields_and_protected_issue_are_rejected(self):
        for key in ("selected_issue", "conflicting_prs", "candidate_count",
                    "status", "reason", "dispatch_allowed"):
            raw = self.valid()
            del raw[key]
            with self.subTest(key=key):
                result = self.run_evidence("success", raw)["result"]
                self.assertEqual("DIAGNOSTIC_OUTPUT_INVALID_OR_MISSING", result["reason"])
                self.assertIsNone(result["candidate_count"])
        result = self.run_evidence("success", dict(self.valid(), selected_issue=79))["result"]
        self.assertEqual("DIAGNOSTIC_OUTPUT_INVALID_OR_MISSING", result["reason"])
        self.assertIsNone(result["selected_issue"])

    def test_skipped_or_failed_step_never_claims_zero_candidates(self):
        for outcome, reason in [("skipped", "DIAGNOSTIC_NOT_COMPLETED"),
                                ("failure", "DIAGNOSTIC_FAILED")]:
            with self.subTest(outcome=outcome):
                result = self.run_evidence(outcome, self.valid())["result"]
                self.assertEqual(reason, result["reason"])
                self.assertIsNone(result["candidate_count"])
                self.assertIs(result["dispatch_allowed"], False)

    def test_missing_or_unsafe_output_fails_closed(self):
        for raw in [None, dict(self.valid(), dispatch_allowed=True),
                    dict(self.valid(), reason="untrusted raw text"),
                    dict(self.valid(), candidate_count=True)]:
            with self.subTest(raw=raw):
                result = self.run_evidence("success", raw)["result"]
                self.assertEqual("DIAGNOSTIC_OUTPUT_INVALID_OR_MISSING", result["reason"])
                self.assertIsNone(result["candidate_count"])
                self.assertIs(result["dispatch_allowed"], False)

    def test_workflow_has_read_only_scope_and_always_preserves_only_sanitized_file(self):
        permissions = self.workflow.split("permissions:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual({"contents: read", "issues: read", "pull-requests: read"},
                         {line.strip() for line in permissions.splitlines()})
        for step in ["Preserve sanitized run evidence and summary", "Upload sanitized pilot evidence"]:
            self.assertIn("- name: " + step + "\n        if: always()", self.workflow)
        self.assertIn("path: /tmp/owner-pilot-evidence/result.json", self.workflow)
        self.assertIn("if-no-files-found: error", self.workflow)
        self.assertNotIn("gh workflow run", self.workflow)
        self.assertNotIn("gh api -X POST", self.workflow)


if __name__ == "__main__":
    unittest.main()
