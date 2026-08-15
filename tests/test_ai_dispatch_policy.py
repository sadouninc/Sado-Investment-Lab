from scripts.ai_dispatch_policy import (
    create_dispatch_lease,
    evaluate_dispatch_result,
    lease_is_expired,
)


def test_create_dispatch_lease_has_60_minute_default_ttl():
    result = create_dispatch_lease(
        issue_number=700,
        engine="copilot",
        assigned_at="2026-08-16T00:00:00Z",
    )
    assert result["status"] == "LEASE_CREATED"
    lease = result["lease"]
    assert lease["work_ref"] == "issue:700"
    assert lease["lease_expires_at"] == "2026-08-16T01:00:00Z"
    assert lease["fallback_owner"] == "sora"


def test_issue_79_is_never_dispatched():
    result = create_dispatch_lease(
        issue_number=79,
        engine="copilot",
        assigned_at="2026-08-16T00:00:00Z",
    )
    assert result == {"status": "PROTECTED_ISSUE_79", "lease": None}


def test_validated_copilot_patch_routes_to_promotion():
    result = evaluate_dispatch_result(
        {
            "issue_number": 700,
            "engine": "copilot",
            "run_success": True,
            "outcome": "REVIEW_READY_VALIDATED",
        }
    )
    assert result["action"] == "PROMOTE_PATCH"


def test_copilot_capacity_failure_falls_back_to_amazon_q_free():
    result = evaluate_dispatch_result(
        {
            "issue_number": 700,
            "engine": "copilot",
            "run_success": False,
            "outcome": "COPILOT_AUTH_OR_QUOTA_BLOCKED",
        }
    )
    assert result["action"] == "FALLBACK_AMAZON_Q_FREE"


def test_contract_failure_never_falls_back_to_another_model():
    result = evaluate_dispatch_result(
        {
            "issue_number": 700,
            "engine": "copilot",
            "run_success": False,
            "outcome": "BLOCKED_CONTRACT_PREFLIGHT",
        }
    )
    assert result == {
        "status": "BLOCK",
        "action": "NONE",
        "reason": "BLOCKED_CONTRACT_PREFLIGHT",
    }


def test_expired_unacked_lease_is_detected():
    lease = create_dispatch_lease(
        issue_number=700,
        engine="copilot",
        assigned_at="2026-08-16T00:00:00Z",
    )["lease"]
    assert lease_is_expired(lease, now="2026-08-16T01:00:00Z") is True


def test_acknowledged_lease_does_not_expire():
    lease = create_dispatch_lease(
        issue_number=700,
        engine="copilot",
        assigned_at="2026-08-16T00:00:00Z",
    )["lease"]
    lease["acknowledged_at"] = "2026-08-16T00:10:00Z"
    assert lease_is_expired(lease, now="2026-08-16T02:00:00Z") is False
