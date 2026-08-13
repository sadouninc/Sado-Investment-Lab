from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.developing_signal_registry import append_observation
from scripts.developing_signal_store import read_store, write_signal
from scripts.investment_seed import transition_seed, validate_seed
from scripts.investment_seed_signal_adapter import promote_seed_to_signal


def make_seed(status: str = "VALIDATING") -> dict:
    seed = validate_seed({
        "observed_at": "2026-08-13T09:15:00+09:00",
        "updated_at": "2026-08-13T09:15:00+09:00",
        "source_sensor": "ASAHI",
        "signal_type": "TECHNOLOGY",
        "observation": "AI設備投資の評価軸にROI言及が増えた",
        "inference": "需要量だけでなく投資効率が次の確認軸になる可能性",
        "source_refs": ["github:issue:356#seed-fixture"],
        "related_seed_refs": [],
        "related_issue_refs": ["#356", "#170"],
        "status": "SEED",
    })
    if status == "SEED":
        return seed
    return transition_seed(seed, "VALIDATING", at="2026-08-13T09:16:00+09:00")


def promote(seed: dict, path):
    return promote_seed_to_signal(
        seed,
        promoted_at="2026-08-13T09:20:00+09:00",
        signal_type="THEME",
        title="AI設備投資のROI評価軸",
        related_entities=[{"type": "THEME", "id": "AI_DATA_CENTER"}],
        why_continued_observation="複数社のCAPEX判断へ波及するか継続観測するため",
        next_checkpoint=None,
        checkpoint_reason="次の主要AI企業決算まで日付未確定",
        signal_path=path,
    )


def test_valid_promotion_writes_exactly_one_signal_with_lineage(tmp_path):
    path = tmp_path / "signals.jsonl"
    seed = make_seed()
    promoted = promote(seed, path)
    result = read_store(path)
    assert result.status == "OK"
    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal["origin_seed_ref"] == seed["seed_id"]
    assert signal["origin_seed_projection_fingerprint"]
    assert promoted["promotion_ref"] == signal["signal_id"]
    assert promoted["status"] == "PROMOTED_TO_SIGNAL"
    assert signal["first_observed_at"] == seed["observed_at"]
    assert signal["last_observed_at"] == seed["observed_at"]
    assert signal["source_refs"] == seed["source_refs"]


def test_signal_projection_does_not_copy_seed_raw_or_inference_payload(tmp_path):
    path = tmp_path / "signals.jsonl"
    seed = make_seed()
    promote(seed, path)
    signal = read_store(path).signals[0]
    assert "inference" not in signal
    assert "related_seed_refs" not in signal
    assert "related_issue_refs" not in signal
    assert "source_sensor" not in signal
    assert signal["observations"] == []
    assert signal["summary"] == seed["observation"]


def test_retry_after_destination_write_reuses_same_signal(tmp_path):
    path = tmp_path / "signals.jsonl"
    seed = make_seed()
    first = promote(seed, path)
    second = promote(seed, path)
    result = read_store(path)
    assert len(result.signals) == 1
    assert first["promotion_ref"] == second["promotion_ref"]
    assert result.signals[0]["origin_seed_ref"] == seed["seed_id"]


def test_retry_after_signal_observation_update_preserves_signal_authority(tmp_path):
    path = tmp_path / "signals.jsonl"
    seed = make_seed()
    first = promote(seed, path)

    signal = read_store(path).signals[0]
    updated = append_observation(signal, {
        "observed_at": "2026-08-14T09:00:00+09:00",
        "source_ref": "source:follow-up",
        "observation": "後続Evidenceを#170側で観測",
        "interpretation": None,
        "effect": "STRENGTHENS",
        "actor": "REI",
    })
    updated["source_refs"].append("source:follow-up")
    write_signal(updated, path)

    second = promote(seed, path)
    final = read_store(path).signals[0]
    assert len(read_store(path).signals) == 1
    assert first["promotion_ref"] == second["promotion_ref"] == final["signal_id"]
    assert final["last_observed_at"] == "2026-08-14T09:00:00+09:00"
    assert len(final["observations"]) == 1
    assert "source:follow-up" in final["source_refs"]


def test_retry_of_already_promoted_seed_is_idempotent(tmp_path):
    path = tmp_path / "signals.jsonl"
    seed = make_seed()
    promoted = promote(seed, path)
    retry = promote(promoted, path)
    assert retry == promoted
    assert len(read_store(path).signals) == 1


def test_rejected_and_unvalidated_seed_fail_closed_without_signal(tmp_path):
    path = tmp_path / "signals.jsonl"
    raw = make_seed("SEED")
    with pytest.raises(ValueError, match="VALIDATING"):
        promote(raw, path)
    assert read_store(path).status == "MISSING"

    validating = make_seed()
    rejected = transition_seed(
        validating,
        "REJECTED",
        at="2026-08-13T09:18:00+09:00",
        rejection_reason="追跡価値不足",
    )
    with pytest.raises(ValueError, match="REJECTED"):
        promote(rejected, path)
    assert read_store(path).status == "MISSING"


def test_destination_failure_does_not_return_or_mutate_promoted_seed(tmp_path):
    path = tmp_path / "signals.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    seed = make_seed()
    original = deepcopy(seed)
    with pytest.raises(ValueError, match="PARTIAL"):
        promote(seed, path)
    assert seed == original
    assert seed["status"] == "VALIDATING"


def test_changed_retry_payload_fails_closed_instead_of_second_signal(tmp_path):
    path = tmp_path / "signals.jsonl"
    seed = make_seed()
    promote(seed, path)
    with pytest.raises(ValueError, match="different Signal payload"):
        promote_seed_to_signal(
            seed,
            promoted_at="2026-08-13T09:20:00+09:00",
            signal_type="THEME",
            title="変更された別タイトル",
            related_entities=[{"type": "THEME", "id": "AI_DATA_CENTER"}],
            why_continued_observation="複数社のCAPEX判断へ波及するか継続観測するため",
            checkpoint_reason="次の主要AI企業決算まで日付未確定",
            signal_path=path,
        )
    assert len(read_store(path).signals) == 1


def test_missing_checkpoint_keeps_unknown_reason_instead_of_inventing_date(tmp_path):
    path = tmp_path / "signals.jsonl"
    promote(make_seed(), path)
    signal = read_store(path).signals[0]
    assert signal["next_checkpoint"] is None
    assert signal["checkpoint_reason"] == "次の主要AI企業決算まで日付未確定"
