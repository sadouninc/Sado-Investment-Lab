from scripts.sora_recovery_stop_attestation import verify_stop_attestation

LEASE = "lease-" + "a" * 32
OWNER = "repo-owner"
REPO = "https://api.github.com/repos/sadouninc/Sado-Investment-Lab/issues/859"


def fixtures():
    prior = [{"lease_id": LEASE, "writer_run_id": 123}]
    comments = [{
        "id": 42,
        "user": {"login": OWNER},
        "issue_url": REPO,
        "body": f"<!-- SORA_RECOVERY_EXECUTOR_STOP issue=859 lease={LEASE} writer_run=123 decision=ALL_EXECUTORS_STOPPED -->",
    }]
    runs = {123: {
        "id": 123, "status": "completed", "conclusion": "success",
        "path": ".github/workflows/sora-recovery-control-plane.yml",
    }}
    return {
        "issue_number": 859, "previous_leases": prior,
        "owner_comments": comments, "actions_runs": runs,
        "expected_owner_login": OWNER, "owner_identity_verified": True,
    }


def test_matching_terminal_run_and_owner_stop():
    result = verify_stop_attestation(**fixtures())
    assert result["verified"] is True
    assert result["all_prior_executors_stopped"] is True
    assert result["prior_dispatch_count"] == 1


def test_expiry_or_active_run_is_not_stop_proof():
    x = fixtures()
    x["actions_runs"][123]["status"] = "in_progress"
    assert verify_stop_attestation(**x)["verified"] is False


def test_unverified_owner_is_not_stop_proof():
    x = fixtures()
    x["owner_identity_verified"] = False
    assert verify_stop_attestation(**x)["verified"] is False


def test_wrong_lease_does_not_clear_prior_dispatch():
    x = fixtures()
    x["previous_leases"][0]["lease_id"] = "lease-" + "b" * 32
    assert verify_stop_attestation(**x)["verified"] is False


def test_duplicate_stop_comments_rejected():
    x = fixtures()
    x["owner_comments"].append({**x["owner_comments"][0], "id": 43})
    assert verify_stop_attestation(**x)["reason"] == "MISSING_OR_DUPLICATE_STOP_ATTESTATION"


def test_all_prior_leases_must_be_stopped():
    x = fixtures()
    x["previous_leases"].append({"lease_id": "lease-" + "b" * 32, "writer_run_id": 124})
    x["actions_runs"][124] = {**x["actions_runs"][123], "id": 124}
    assert verify_stop_attestation(**x)["verified"] is False


def test_protected_issue_denied():
    x = fixtures()
    x["issue_number"] = 79
    assert verify_stop_attestation(**x)["verified"] is False


def test_wrong_owner_rejected():
    x = fixtures()
    x["owner_comments"][0]["user"]["login"] = "other-user"
    assert verify_stop_attestation(**x)["verified"] is False
