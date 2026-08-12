from __future__ import annotations

import json
from pathlib import Path

from scripts.morning_scheduler_guard import recovery_decision


WORKFLOW = Path(".github/workflows/ai-morning-analyst.yml")


def _paths(tmp_path: Path, as_of: str = "2026-08-12") -> tuple[Path, Path]:
    return tmp_path / f"{as_of}.md", tmp_path / f"{as_of}.json"


def test_missing_primary_run_artifacts_trigger_fallback(tmp_path: Path):
    report, diagnostic = _paths(tmp_path)
    assert recovery_decision(
        as_of="2026-08-12", report_path=report, diagnostic_path=diagnostic
    ) == {"action": "RUN", "reason": "REPORT_MISSING"}


def test_successful_primary_makes_fallback_noop(tmp_path: Path):
    report, diagnostic = _paths(tmp_path)
    report.write_text("# AI Morning Report\n", encoding="utf-8")
    diagnostic.write_text(
        json.dumps(
            {
                "status": "OK",
                "dataset_as_of": "2026-08-12",
                "report_path": str(report).replace("\\", "/"),
            }
        ),
        encoding="utf-8",
    )
    assert recovery_decision(
        as_of="2026-08-12", report_path=report, diagnostic_path=diagnostic
    ) == {"action": "NOOP", "reason": "TODAY_ALREADY_GENERATED"}


def test_corrupt_or_wrong_date_diagnostic_fails_closed_to_rerun(tmp_path: Path):
    report, diagnostic = _paths(tmp_path)
    report.write_text("# AI Morning Report\n", encoding="utf-8")
    diagnostic.write_text("not-json", encoding="utf-8")
    assert recovery_decision(
        as_of="2026-08-12", report_path=report, diagnostic_path=diagnostic
    )["reason"] == "DIAGNOSTIC_MISSING_OR_INVALID"

    diagnostic.write_text(
        json.dumps({"status": "OK", "dataset_as_of": "2026-08-11"}),
        encoding="utf-8",
    )
    assert recovery_decision(
        as_of="2026-08-12", report_path=report, diagnostic_path=diagnostic
    )["reason"] == "DATASET_DATE_MISMATCH"


def test_workflow_has_jst_recovery_schedule_and_idempotency_guard():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "45 23 * * 0-4"' in workflow
    assert 'cron: "10 0 * * 1-5"' in workflow
    assert "python3 scripts/morning_scheduler_guard.py" in workflow
    assert workflow.count("if: steps.recovery.outputs.should_generate == 'true'") >= 11
