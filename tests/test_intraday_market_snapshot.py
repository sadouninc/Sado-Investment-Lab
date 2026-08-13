from datetime import date, datetime, timezone

import pytest

from scripts.intraday_market_snapshot import (
    SESSION_SLOTS,
    build_snapshot,
    calculate_delta,
    persist_snapshot,
)
from scripts.morning_dataset.providers.base import ProviderResult


def result(*, value=100.0, status="OK", as_of="2026-08-13T01:00:00+00:00"):
    return ProviderResult(
        status=status,
        data={"indices": {"nikkei225": {"value": value}}},
        as_of=as_of,
        source_reference="test",
        reason=None,
    )


def snapshot(slot="MORNING", *, value=100.0, previous=None, morning=None, status="OK", as_of="2026-08-13T01:00:00+00:00"):
    return build_snapshot(
        result(value=value, status=status, as_of=as_of),
        business_date=date(2026, 8, 13),
        session_slot=slot,
        observed_at=datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc),
        previous=previous,
        morning=morning,
    )


def test_four_semantic_slots_are_stable():
    assert SESSION_SLOTS == ("MORNING", "MIDDAY", "AFTERNOON", "CLOSE")


def test_previous_and_morning_delta_are_separate():
    morning = snapshot(value=100.0)
    midday = snapshot("MIDDAY", value=105.0, previous=morning, morning=morning)
    afternoon = snapshot("AFTERNOON", value=110.0, previous=midday, morning=morning)
    assert afternoon["delta_from_previous"]["fields"]["indices.nikkei225"]["absolute"] == 5.0
    assert afternoon["delta_from_morning"]["fields"]["indices.nikkei225"]["absolute"] == 10.0


def test_missing_base_does_not_invent_zero_delta():
    current = snapshot("MIDDAY", value=105.0)
    assert current["delta_from_previous"] is None
    assert current["delta_from_morning"] is None
    assert calculate_delta(None, current) is None


def test_stale_source_fails_closed():
    stale = snapshot(as_of="2026-08-12T01:00:00+00:00")
    assert stale["source_status"] == "STALE"


def test_retry_is_idempotent_and_conflict_is_rejected(tmp_path):
    first = snapshot(value=100.0)
    persist_snapshot(tmp_path, first)
    persist_snapshot(tmp_path, first)
    conflicting = snapshot(value=101.0)
    with pytest.raises(ValueError, match="conflicting observation"):
        persist_snapshot(tmp_path, conflicting)


def test_snapshot_never_emits_trade_action_or_ai_trigger():
    current = snapshot(value=100.0)
    assert current["meaningful_delta"] is False
    assert current["review_reasons"] == []
    assert "trade_action" not in current
    assert "ai_trigger" not in current
