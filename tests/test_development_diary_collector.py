"""Tests for Development Diary Collector - Issue #726 acceptance criteria."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.development_diary_collector import (
    DailyCollector,
    calc_window,
    get_executor,
    get_task_class,
    in_range,
    load_schema,
    validate_snapshot,
)

JST = ZoneInfo("Asia/Tokyo")


class TestJSTBoundaries:
    """JST day-boundary fixtures."""
    
    def test_window_calculation(self):
        diary_dt = date(2026, 8, 19)
        start, end = calc_window(diary_dt)
        
        assert start == datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        assert end == datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
    
    def test_23_59_59_in_target_day(self):
        """23:59:59 JST is in target day."""
        diary_dt = date(2026, 8, 19)
        start, end = calc_window(diary_dt)
        
        ts = datetime(2026, 8, 19, 23, 59, 59, tzinfo=JST)
        assert in_range(ts, start, end) is True
    
    def test_00_00_00_in_next_day(self):
        """00:00:00 JST is NOT in target day (half-open interval)."""
        diary_dt = date(2026, 8, 19)
        start, end = calc_window(diary_dt)
        
        ts = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        assert in_range(ts, start, end) is False


class TestEventDeduplication:
    """Same event rerun: no count increase."""
    
    def test_pr_processed_twice(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        pr = {
            "number": 42,
            "created_at": "2026-08-19T10:00:00Z",
            "merged_at": None,
            "closed_at": None,
            "user": {"login": "test"},
            "labels": [],
        }
        
        coll.process_pr(pr)
        first_count = coll.pr_open_cnt
        
        coll.process_pr(pr)
        assert coll.pr_open_cnt == first_count


class TestDispatchedAcked:
    """DISPATCHED/ACKED alone: no implementation_start_count."""
    
    def test_dispatched_no_impl_start(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        coll.record_dispatch("alice", "TASK")
        
        assert coll.impl_start_cnt == 0
        assert coll.waiting_cnt == 1
    
    def test_acked_no_impl_start(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        coll.record_ack("bob", "TASK")
        
        assert coll.impl_start_cnt == 0


class TestExecutionEvidence:
    """Execution evidence: correct executor/task_class attribution."""
    
    def test_execution_evidence_counts(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        coll.record_execution_evidence("charlie", "FEATURE")
        
        assert coll.impl_start_cnt == 1
        assert coll.active_wip == 1
    
    def test_executor_task_class_lossless(self):
        """Same executor, different task_class: separate records."""
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        coll.record_execution_evidence("dave", "DOCS")
        coll.record_execution_evidence("dave", "CODE")
        
        snap = coll.generate_snapshot(
            date(2026, 8, 19), 
            datetime(2026, 8, 20, 0, 10, 0, tzinfo=JST)
        )
        
        perf = snap["executor_performance"]
        assert len(perf) == 2
        
        keys = {(p["executor"], p["task_class"]) for p in perf}
        assert ("dave", "DOCS") in keys
        assert ("dave", "CODE") in keys


class TestUnavailableMetrics:
    """Unavailable cost/credits: null not 0."""
    
    def test_null_for_unavailable(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        snap = coll.generate_snapshot(
            date(2026, 8, 19), 
            datetime(2026, 8, 20, 0, 10, 0, tzinfo=JST)
        )
        
        econ = snap["economics"]
        assert econ["copilot_credits"] is None
        assert econ["ai_cost_per_merge"] is None
        
        # Observed zero vs unavailable
        assert econ["paid_fallback_count"] == 0


class TestLateEvidenceCorrection:
    """Late evidence: exactly one correction audit record."""
    
    def test_correction_no_duplicate(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        recorded = datetime(2026, 8, 20, 0, 20, 0, tzinfo=JST)
        refs = ["pr:#999"]
        
        coll.add_correction("late merge detected", refs, recorded)
        assert len(coll.corrections) == 1
        
        # Duplicate
        coll.add_correction("late merge detected", refs, recorded)
        assert len(coll.corrections) == 1
    
    def test_correction_fields(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        recorded = datetime(2026, 8, 20, 0, 15, 0, tzinfo=JST)
        refs = ["issue:#123"]
        
        coll.add_correction("late close", refs, recorded)
        
        corr = coll.corrections[0]
        assert "correction_id" in corr
        assert corr["reason"] == "late close"
        assert corr["evidence_refs"] == refs
        assert "recorded_at" in corr


class TestInvalidSnapshot:
    """Invalid snapshot: fail before persistence."""
    
    def test_negative_count_rejected(self):
        invalid = {
            "schema_version": "1.0",
            "diary_date_jst": "2026-08-19",
            "closed_at_jst": "2026-08-20T00:10:00+09:00",
            "source_window_start_jst": "2026-08-19T00:00:00+09:00",
            "source_window_end_jst": "2026-08-20T00:00:00+09:00",
            "factory_output": {
                "ready_count": -5,  # Invalid
                "implementation_start_count": 0,
                "pr_opened": 0,
                "pr_merged": 0,
                "pr_closed_unmerged": 0,
                "durable_output_count": 0,
                "productive_step_count": 0,
                "lead_time_minutes": None,
            },
            "executor_performance": [],
            "flow_health": {
                "active_implementation_wip": 0,
                "waiting_work_count": 0,
                "ready_nonconflicting_count": 0,
                "queue_replenish_latency_minutes": None,
                "path_owner_conflict_count": 0,
                "ci_stall_count": 0,
                "starvation_state": "OK",
                "blocked_escape_count": 0,
                "human_intervention_count": 0,
                "durable_output_interval_minutes": None,
            },
            "economics": {
                "free_executor_ratio": None,
                "paid_fallback_count": 0,
                "copilot_usage_count": None,
                "copilot_credits": None,
                "ai_cost_per_accepted_unit": None,
                "ai_cost_per_merge": None,
            },
            "factory_capability_changes": [],
            "corrections": [],
        }
        
        with pytest.raises(Exception):
            validate_snapshot(invalid)


class TestSchemaContract:
    """Use #725 schema validator (no independent schema)."""
    
    def test_schema_loaded_from_file(self):
        sch = load_schema()
        assert sch["$id"] == "development-diary-daily-v1.schema.json"


class TestHelpers:
    """Helper function tests."""
    
    def test_executor_extraction(self):
        assert get_executor({"user": {"login": "alice"}}) == "alice"
        assert get_executor({"user": {"login": "copilot-bot"}}) == "COPILOT"
        assert get_executor({"user": {"login": "dependabot"}}) == "DEPENDABOT"
        assert get_executor({"user": {}}) == "UNKNOWN"
    
    def test_task_class_mapping(self):
        assert get_task_class([{"name": "docs"}]) == "DOCS"
        assert get_task_class([{"name": "bug"}]) == "BUGFIX"
        assert get_task_class([{"name": "feature"}]) == "FEATURE"
        assert get_task_class([]) == "GENERAL"
    
    def test_pr_opened_counted(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        pr = {
            "number": 1,
            "created_at": "2026-08-19T12:00:00Z",
            "merged_at": None,
            "closed_at": None,
            "user": {"login": "tester"},
            "labels": [],
        }
        
        coll.process_pr(pr)
        assert coll.pr_open_cnt == 1
    
    def test_pr_merged_counted(self):
        start = datetime(2026, 8, 19, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 8, 20, 0, 0, 0, tzinfo=JST)
        coll = DailyCollector(start, end)
        
        pr = {
            "number": 2,
            "created_at": "2026-08-18T12:00:00Z",
            "merged_at": "2026-08-19T14:00:00Z",
            "closed_at": "2026-08-19T14:00:00Z",
            "user": {"login": "tester"},
            "labels": [],
        }
        
        coll.process_pr(pr)
        assert coll.pr_merge_cnt == 1
