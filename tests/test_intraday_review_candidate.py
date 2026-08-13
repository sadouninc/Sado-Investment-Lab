from scripts.intraday_review_candidate import project_review_candidate


def snapshot(*, source_status="OK", meaningful_delta=False, review_reasons=None):
    return {
        "identity": "2026-08-13:MIDDAY",
        "business_date": "2026-08-13",
        "session_slot": "MIDDAY",
        "observed_at": "2026-08-13T11:40:00+09:00",
        "source_status": source_status,
        "meaningful_delta": meaningful_delta,
        "review_reasons": [] if review_reasons is None else review_reasons,
        "delta_from_previous": {"fields": {}},
        "delta_from_morning": {"fields": {}},
    }


def test_explicit_meaningful_delta_with_reason_projects_review_required():
    result = project_review_candidate(
        snapshot(meaningful_delta=True, review_reasons=["existing-threshold-transition"])
    )
    assert result["state"] == "REVIEW_REQUIRED"
    assert result["review_required"] is True
    assert result["mutation_performed"] is False


def test_meaningful_delta_without_explicit_reason_does_not_invent_trigger():
    result = project_review_candidate(snapshot(meaningful_delta=True, review_reasons=[]))
    assert result["state"] == "NO_REVIEW_REQUIRED"
    assert result["review_required"] is False


def test_invalid_reason_values_do_not_invent_trigger():
    invalid_reasons = [None, 0, 1.5, {}, [], "", "   "]
    for reason in invalid_reasons:
        result = project_review_candidate(
            snapshot(meaningful_delta=True, review_reasons=[reason])
        )
        assert result["state"] == "NO_REVIEW_REQUIRED"
        assert result["review_required"] is False
        assert result["review_reasons"] == []


def test_valid_reason_is_trimmed_and_invalid_values_are_dropped():
    result = project_review_candidate(
        snapshot(
            meaningful_delta=True,
            review_reasons=[None, "  existing-threshold-transition  ", 42, "   "],
        )
    )
    assert result["state"] == "REVIEW_REQUIRED"
    assert result["review_required"] is True
    assert result["review_reasons"] == ["existing-threshold-transition"]


def test_non_list_reasons_fail_closed():
    for reasons in (None, "existing-threshold-transition", {"reason": "x"}, 42):
        result = project_review_candidate(
            snapshot(meaningful_delta=True, review_reasons=reasons)
        )
        assert result["state"] == "NO_REVIEW_REQUIRED"
        assert result["review_required"] is False
        assert result["review_reasons"] == []


def test_non_ok_source_fails_closed_even_when_upstream_flag_is_true():
    for status in ("PARTIAL", "STALE", "MISSING"):
        result = project_review_candidate(
            snapshot(
                source_status=status,
                meaningful_delta=True,
                review_reasons=["existing-threshold-transition"],
            )
        )
        assert result["state"] == "DATA_QUALITY_BLOCKED"
        assert result["review_required"] is False


def test_no_change_is_read_only_noop():
    result = project_review_candidate(snapshot())
    assert result["state"] == "NO_REVIEW_REQUIRED"
    assert result["review_required"] is False
    assert "trade_action" not in result
    assert "buy" not in result
    assert "sell" not in result


def test_projection_preserves_delta_evidence_without_recalculation():
    source = snapshot()
    result = project_review_candidate(source)
    assert result["delta_from_previous"] is source["delta_from_previous"]
    assert result["delta_from_morning"] is source["delta_from_morning"]
