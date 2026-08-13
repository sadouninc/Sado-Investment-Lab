import pytest

from scripts.investment_seed import (
    SeedRegistry,
    deterministic_seed_id,
    promotion_payload,
    transition_seed,
    validate_seed,
)


def seed(**overrides):
    base = {
        "observed_at": "2026-08-13T08:10:00+09:00",
        "updated_at": "2026-08-13T08:10:00+09:00",
        "source_sensor": "ASAHI",
        "signal_type": "CAPEX",
        "observation": "AI data-center transformer lead times extended in a primary source.",
        "inference": "Power equipment may deserve continued observation.",
        "source_refs": ["primary:example:1"],
        "related_seed_refs": [],
        "related_issue_refs": ["issue:350"],
        "status": "SEED",
    }
    base.update(overrides)
    return base


def test_deterministic_identity_and_exact_retry_are_idempotent():
    first = validate_seed(seed())
    second = validate_seed(seed())
    assert first["seed_id"] == second["seed_id"]

    registry = SeedRegistry()
    assert registry.ingest(first)["outcome"] == "INSERTED"
    assert registry.ingest(second)["outcome"] == "UNCHANGED"


def test_same_identity_with_different_payload_fails_closed():
    registry = SeedRegistry()
    original = validate_seed(seed())
    registry.ingest(original)
    conflicting = dict(original)
    conflicting["inference"] = "Different inference under the same immutable identity."
    with pytest.raises(ValueError, match="identity conflict"):
        registry.ingest(conflicting)


def test_identity_is_not_title_similarity_based():
    first = deterministic_seed_id(
        observed_at="2026-08-13T08:10:00+09:00",
        source_sensor="ASAHI",
        signal_type="CAPEX",
        observation="Transformer lead time extended.",
        source_refs=["primary:a"],
    )
    second = deterministic_seed_id(
        observed_at="2026-08-13T08:10:00+09:00",
        source_sensor="ASAHI",
        signal_type="CAPEX",
        observation="Transformer lead time extended.",
        source_refs=["primary:b"],
    )
    assert first != second


def test_observation_and_inference_must_remain_distinct():
    with pytest.raises(ValueError, match="inference must remain distinct"):
        validate_seed(seed(inference=seed()["observation"]))


def test_malformed_provenance_is_rejected():
    with pytest.raises(ValueError, match="source_refs must contain"):
        validate_seed(seed(source_refs=[]))
    with pytest.raises(ValueError, match="source_refs entry"):
        validate_seed(seed(source_refs=[""]))


def test_rejection_requires_reason():
    validating = transition_seed(seed(), "VALIDATING", at="2026-08-13T08:20:00+09:00")
    with pytest.raises(ValueError, match="rejection_reason"):
        transition_seed(validating, "REJECTED", at="2026-08-13T08:30:00+09:00")
    rejected = transition_seed(
        validating,
        "REJECTED",
        at="2026-08-13T08:30:00+09:00",
        rejection_reason="Duplicate primary evidence; no new information.",
    )
    assert rejected["status"] == "REJECTED"


def test_promotion_requires_ref_and_cannot_skip_validation():
    validating = transition_seed(seed(), "VALIDATING", at="2026-08-13T08:20:00+09:00")
    with pytest.raises(ValueError, match="promotion_ref"):
        transition_seed(validating, "PROMOTED_TO_SIGNAL", at="2026-08-13T08:30:00+09:00")

    with pytest.raises(ValueError, match="invalid seed transition"):
        transition_seed(seed(), "PROMOTED_TO_SIGNAL", at="2026-08-13T08:30:00+09:00", promotion_ref="signal:x")


def test_terminal_seed_cannot_roll_back():
    validating = transition_seed(seed(), "VALIDATING", at="2026-08-13T08:20:00+09:00")
    rejected = transition_seed(
        validating,
        "REJECTED",
        at="2026-08-13T08:30:00+09:00",
        rejection_reason="Weak provenance.",
    )
    with pytest.raises(ValueError, match="terminal seed cannot transition"):
        transition_seed(rejected, "SEED", at="2026-08-13T08:40:00+09:00")


def test_promotion_handoff_is_minimal_and_requires_checkpoint_reason_when_unknown():
    validating = transition_seed(seed(), "VALIDATING", at="2026-08-13T08:20:00+09:00")
    promoted = transition_seed(
        validating,
        "PROMOTED_TO_SIGNAL",
        at="2026-08-13T08:30:00+09:00",
        promotion_ref="signal:pending:1",
    )
    with pytest.raises(ValueError, match="checkpoint_reason"):
        promotion_payload(
            promoted,
            title="AI/DC power equipment lead-time signal",
            related_entity_candidates=[{"type": "THEME", "id": "AI_DC"}],
            why_continued_observation="A repeatable supply constraint could reach company orders.",
        )

    payload = promotion_payload(
        promoted,
        title="AI/DC power equipment lead-time signal",
        related_entity_candidates=[{"type": "THEME", "id": "AI_DC"}],
        why_continued_observation="A repeatable supply constraint could reach company orders.",
        checkpoint_reason="UNKNOWN until the next company order disclosure.",
    )
    assert payload["origin_seed_ref"] == promoted["seed_id"]
    assert payload["observation_summary"] == promoted["observation"]
    assert "inference" not in payload
    assert "status" not in payload
    assert payload["source_refs"] == ["primary:example:1"]
