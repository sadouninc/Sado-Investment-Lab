from scripts.decision_timing import aggregate_latency, build_timing_projection


EPISODE = {"episode_id": "episode:6622:test", "security_code": "6622"}


def event(kind, at, ref, **extra):
    return {"kind": kind, "observed_at": at, "source_ref": ref, "authority": "EXPLICIT", **extra}


def test_full_milestone_chain_and_timezone_aware_duration():
    events = [
        event("DISCOVERY", "2026-08-01T09:00:00+09:00", "candidate:1"),
        event("RESEARCH_STARTED", "2026-08-02T09:00:00+09:00", "research:1"),
        event("CURRENT_RESEARCH", "2026-08-05T09:00:00+09:00", "research:2"),
        event("HYPOTHESIS_CREATED", "2026-08-03T15:00:00+09:00", "thesis:1"),
        event("VALUATION_CREATED", "2026-08-04T09:00:00+09:00", "valuation:1"),
        event("DECISION", "2026-08-05T18:00:00+09:00", "decision:1"),
        event("MATERIAL_EVIDENCE", "2026-08-05T00:00:00Z", "revision:1"),
        event("REVIEW_STARTED", "2026-08-05T12:00:00Z", "review:1"),
        event("DECISION_RECONSIDERED", "2026-08-05T15:00:00Z", "decision:2"),
    ]
    result = build_timing_projection(EPISODE, events, as_of="2026-08-06T00:00:00Z")
    assert result["status"] == "COMPLETE"
    assert result["latencies"]["discovery_to_research_hours"] == 24.0
    assert result["latencies"]["research_to_hypothesis_hours"] == 30.0
    assert result["latencies"]["material_change_to_review_hours"] == 12.0


def test_missing_discovery_is_partial_and_never_zero_latency():
    result = build_timing_projection(
        EPISODE,
        [event("RESEARCH_STARTED", "2026-08-02T09:00:00+09:00", "research:1"), event("DECISION", "2026-08-05T09:00:00+09:00", "decision:1")],
        as_of="2026-08-06T00:00:00+09:00",
    )
    assert result["status"] == "PARTIAL"
    assert result["milestones"]["first_discovered_at"] is None
    assert result["latencies"]["discovery_to_research_hours"] is None


def test_missing_decision_is_partial():
    result = build_timing_projection(
        EPISODE,
        [event("RESEARCH_STARTED", "2026-08-02T09:00:00+09:00", "research:1"), event("HYPOTHESIS_CREATED", "2026-08-03T09:00:00+09:00", "thesis:1")],
        as_of="2026-08-06T00:00:00+09:00",
    )
    assert result["status"] == "PARTIAL"
    assert result["latencies"]["hypothesis_to_decision_hours"] is None


def test_future_source_is_excluded():
    result = build_timing_projection(
        EPISODE,
        [event("DISCOVERY", "2026-08-10T09:00:00+09:00", "future:1"), event("RESEARCH_STARTED", "2026-08-02T09:00:00+09:00", "research:1")],
        as_of="2026-08-09T00:00:00+09:00",
    )
    assert result["milestones"]["first_discovered_at"] is None
    assert "future:1" not in str(result["source_refs"])


def test_presentation_only_and_non_material_revision_are_excluded():
    result = build_timing_projection(
        EPISODE,
        [
            event("MATERIAL_EVIDENCE", "2026-08-03T09:00:00+09:00", "presentation:1", presentation_only=True),
            event("MATERIAL_EVIDENCE", "2026-08-04T09:00:00+09:00", "refresh:1", material=False),
            event("MATERIAL_EVIDENCE", "2026-08-05T09:00:00+09:00", "material:1", material=True),
            event("REVIEW_STARTED", "2026-08-05T21:00:00+09:00", "review:1"),
        ],
        as_of="2026-08-06T00:00:00+09:00",
    )
    assert result["milestones"]["latest_material_evidence_at"] == "2026-08-05T09:00:00+09:00"
    assert result["latencies"]["material_change_to_review_hours"] == 12.0


def test_identical_rerun_is_deterministic_and_does_not_mutate_inputs():
    events = [event("DISCOVERY", "2026-08-01T09:00:00+09:00", "candidate:1")]
    before = [dict(events[0])]
    first = build_timing_projection(EPISODE, events, as_of="2026-08-09T00:00:00+09:00")
    second = build_timing_projection(EPISODE, events, as_of="2026-08-09T00:00:00+09:00")
    assert first == second
    assert events == before


def test_transaction_time_is_not_a_decision_source():
    result = build_timing_projection(
        EPISODE,
        [event("RESEARCH_STARTED", "2026-08-02T09:00:00+09:00", "research:1")],
        as_of="2026-08-09T00:00:00+09:00",
        context={"transaction_executed_at": "2026-08-03T09:00:00+09:00"},
    )
    assert result["milestones"]["first_decision_at"] is None


def test_daihen_partial_fixture_is_valid():
    result = build_timing_projection(
        EPISODE,
        [
            event("RESEARCH_STARTED", "2026-08-04T10:00:00+09:00", "company:6622"),
            event("VALUATION_CREATED", "2026-08-05T10:00:00+09:00", "valuation:6622"),
            event("DECISION", "2026-08-06T10:00:00+09:00", "decision:6622"),
        ],
        as_of="2026-08-09T00:00:00+09:00",
        context={"expected_time_horizon": None},
    )
    assert result["security_code"] == "6622"
    assert result["status"] == "PARTIAL"


def test_small_sample_aggregation_never_claims_a_trend():
    assert aggregate_latency([24.0, 48.0]) == {"n": 2, "status": "INSUFFICIENT_DATA", "median_hours": 36.0, "trend": None}
    assert aggregate_latency([24.0, 48.0, 72.0]) == {"n": 3, "status": "OBSERVED", "median_hours": 48.0, "trend": None}
