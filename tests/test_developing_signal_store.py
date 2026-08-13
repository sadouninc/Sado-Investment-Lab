from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.developing_signal_registry import append_observation, deterministic_signal_id, transition_signal
from scripts.developing_signal_store import read_store, write_signal


def make_signal(key="ai-capex", observed_at="2026-08-13T09:00:00+09:00"):
    entities = [{"type": "THEME", "id": "AI_DATA_CENTER"}]
    return {
        "signal_key": key,
        "signal_id": deterministic_signal_id(key, observed_at, entities),
        "title": "AI/DC設備投資の変化",
        "signal_type": "THEME",
        "status": "WATCHING",
        "direction": "UNKNOWN",
        "first_observed_at": observed_at,
        "last_observed_at": observed_at,
        "created_by": "ASAHI",
        "summary": "設備投資の継続観測",
        "why_it_may_matter": "企業受注へ先行する可能性を確認するため",
        "source_refs": ["source:first"],
        "related_entities": entities,
        "observations": [{
            "observed_at": observed_at,
            "source_ref": "source:first",
            "observation": "最初の観測",
            "interpretation": None,
            "effect": "NEUTRAL",
            "actor": "ASAHI",
        }],
        "next_checkpoint": "2026-08-20T09:00:00+09:00",
        "expires_at": None,
        "duplicate_state": "UNIQUE",
    }


def test_missing_and_empty_are_distinct(tmp_path):
    path = tmp_path / "signals.jsonl"
    assert read_store(path).status == "MISSING"
    path.write_text("", encoding="utf-8")
    result = read_store(path)
    assert result.status == "OK"
    assert result.signals == ()


def test_round_trip_append_terminal_and_idempotency(tmp_path):
    path = tmp_path / "signals.jsonl"
    signal = make_signal()
    assert write_signal(signal, path) is True
    assert write_signal(signal, path) is False

    updated = append_observation(read_store(path).signals[0], {
        "observed_at": "2026-08-14T09:00:00+09:00",
        "source_ref": "source:second",
        "observation": "追加観測",
        "interpretation": None,
        "effect": "STRENGTHENS",
        "actor": "REI",
    })
    updated["source_refs"].append("source:second")
    assert write_signal(updated, path) is True

    promoted = transition_signal(read_store(path).signals[0], "PROMOTED", at="2026-08-15T09:00:00+09:00", promotion_ref="research:ai-dc")
    assert write_signal(promoted, path) is True
    final = read_store(path).signals[0]
    assert final["status"] == "PROMOTED"
    assert final["first_observed_at"] == signal["first_observed_at"]
    assert final["source_refs"][0] == "source:first"
    assert len(final["observations"]) == 2


def test_history_and_source_lineage_are_append_only(tmp_path):
    path = tmp_path / "signals.jsonl"
    signal = make_signal()
    write_signal(signal, path)

    changed = deepcopy(signal)
    changed["observations"] = []
    with pytest.raises(ValueError, match="append-only"):
        write_signal(changed, path)

    changed = deepcopy(signal)
    changed["source_refs"] = []
    with pytest.raises(ValueError, match="source lineage"):
        write_signal(changed, path)


def test_malformed_record_is_partial_and_blocks_write(tmp_path):
    path = tmp_path / "signals.jsonl"
    path.write_text(json.dumps(make_signal(), ensure_ascii=False) + "\nnot-json\n", encoding="utf-8")
    result = read_store(path)
    assert result.status == "PARTIAL"
    assert len(result.signals) == 1
    assert result.diagnostics
    with pytest.raises(ValueError, match="PARTIAL"):
        write_signal(make_signal(), path)


def test_reader_orders_active_before_terminal(tmp_path):
    path = tmp_path / "signals.jsonl"
    older = make_signal("older", "2026-08-10T09:00:00+09:00")
    newer = make_signal("newer", "2026-08-12T09:00:00+09:00")
    terminal = transition_signal(make_signal("terminal", "2026-08-13T09:00:00+09:00"), "DISMISSED", at="2026-08-13T10:00:00+09:00", reason="反証優勢")
    write_signal(older, path)
    write_signal(terminal, path)
    write_signal(newer, path)
    assert [item["signal_key"] for item in read_store(path).signals] == ["newer", "older", "terminal"]
