import pytest

from scripts.executor_dispatch_adapters import (
    AMAZON_Q_LABEL,
    JULES_CONTROL_ISSUE,
    already_dispatched,
    build_dispatch_plan,
)


def lease(**overrides):
    data = {
        "lease_id": "lease-abc123",
        "work_ref": "#731",
        "executor": "AMAZON_Q",
    }
    data.update(overrides)
    return data


def test_amazon_q_uses_exact_feature_development_label():
    plan = build_dispatch_plan(lease())
    assert plan.action == "ADD_ISSUE_LABEL"
    assert plan.payload["label"] == AMAZON_Q_LABEL
    assert AMAZON_Q_LABEL == "Amazon Q development agent"
    assert plan.target_issue == 731


def test_jules_reuses_existing_control_plane():
    plan = build_dispatch_plan(lease(executor="JULES", work_ref="#725"))
    assert plan.action == "ARM_JULES_CONTROL"
    assert plan.payload["control_issue"] == JULES_CONTROL_ISSUE == 685
    assert plan.payload["target_issue"] == 725
    assert plan.payload["state"] == "READY_FOR_SCHEDULED_RUN"
    assert plan.payload["run_token"] == "auto-router-lease-abc123"


def test_sora_persists_dispatch_record_without_fake_github_assignee():
    plan = build_dispatch_plan(lease(executor="SORA", work_ref="#724"))
    assert plan.action == "PERSIST_SORA_LEASE"
    assert plan.payload["issue_number"] == 724
    assert plan.payload["state"] == "DISPATCHED"
    assert "assignee" not in plan.payload


def test_evidence_marker_is_deterministic_and_idempotent():
    first = build_dispatch_plan(lease())
    second = build_dispatch_plan(lease())
    assert first.idempotency_key == second.idempotency_key
    assert first.evidence_marker == second.evidence_marker
    comments = [{"body": first.evidence_marker}]
    assert already_dispatched(comments, lease_id="lease-abc123") is True
    assert already_dispatched(comments, lease_id="lease-other") is False


def test_issue_79_is_hard_denied_for_every_executor():
    for executor in ("AMAZON_Q", "JULES", "SORA"):
        with pytest.raises(ValueError, match="hard-denied"):
            build_dispatch_plan(lease(executor=executor, work_ref="#79"))


def test_malformed_work_ref_fails_closed():
    with pytest.raises(ValueError, match="canonical"):
        build_dispatch_plan(lease(work_ref="731"))


def test_missing_lease_id_fails_closed():
    with pytest.raises(ValueError, match="lease_id"):
        build_dispatch_plan(lease(lease_id=""))


def test_unknown_executor_fails_closed():
    with pytest.raises(ValueError, match="unsupported"):
        build_dispatch_plan(lease(executor="COPILOT"))
