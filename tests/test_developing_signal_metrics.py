from scripts.developing_signal_metrics import evaluate_signals
from scripts.developing_signal_registry import deterministic_signal_id


def signal(*, key, status="WATCHING", created_by="ASAHI", first="2026-08-10T00:00:00+00:00", last="2026-08-10T00:00:00+00:00", promoted_at=None, resolved_at=None, reason=None):
    item = {
        "signal_key": key,
        "title": key,
        "summary": "summary",
        "why_it_may_matter": "why",
        "created_by": created_by,
        "signal_type": "MARKET",
        "status": status,
        "direction": "UNKNOWN",
        "first_observed_at": first,
        "last_observed_at": last,
        "related_entities": [],
        "observations": [],
        "source_refs": ["primary:test"],
        "next_checkpoint": "2026-08-20T00:00:00+00:00",
        "duplicate_state": "UNIQUE",
    }
    item["signal_id"] = deterministic_signal_id(key, first, [])
    if promoted_at is not None:
        item["promotion_ref"] = "research:test"
        item["promoted_at"] = promoted_at
    if resolved_at is not None:
        item["resolved_at"] = resolved_at
    if reason is not None:
        item["resolution_reason"] = reason
    return item


def test_empty_population_is_unknown_not_zero_rate():
    result = evaluate_signals([])
    assert result["total"] == 0
    assert result["promotion_rate"] is None
    assert result["dismiss_or_expire_rate"] is None
    assert result["average_promotion_lead_hours"] is None
    assert result["by_sensor"] == {}


def test_counts_rates_and_promotion_lead_time_are_deterministic():
    items = [
        signal(
            key="promoted",
            status="PROMOTED",
            first="2026-08-10T00:00:00+00:00",
            last="2026-08-11T00:00:00+00:00",
            promoted_at="2026-08-12T00:00:00+00:00",
            resolved_at="2026-08-12T00:00:00+00:00",
        ),
        signal(
            key="expired",
            status="EXPIRED",
            created_by="REI",
            resolved_at="2026-08-13T00:00:00+00:00",
            reason="no follow-up evidence",
        ),
        signal(key="watching", created_by="REI"),
    ]
    result = evaluate_signals(items)
    assert result["total"] == 3
    assert result["active"] == 1
    assert result["promoted"] == 1
    assert result["expired"] == 1
    assert result["promotion_rate"] == 1 / 3
    assert result["dismiss_or_expire_rate"] == 1 / 3
    assert result["average_promotion_lead_hours"] == 48.0


def test_sensor_metrics_do_not_infer_quality_from_no_promotions():
    items = [
        signal(key="asahi-promoted", status="PROMOTED", created_by="ASAHI", promoted_at="2026-08-11T00:00:00+00:00", resolved_at="2026-08-11T00:00:00+00:00"),
        signal(key="rei-watch", created_by="REI"),
    ]
    result = evaluate_signals(items)
    assert result["by_sensor"]["ASAHI"]["promotion_rate"] == 1.0
    assert result["by_sensor"]["ASAHI"]["average_promotion_lead_hours"] == 24.0
    assert result["by_sensor"]["REI"]["promotion_rate"] == 0.0
    assert result["by_sensor"]["REI"]["average_promotion_lead_hours"] is None
    assert "quality" not in result["by_sensor"]["REI"]
