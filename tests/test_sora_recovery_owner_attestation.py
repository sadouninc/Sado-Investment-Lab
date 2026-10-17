from scripts.sora_recovery_owner_attestation import inspect_owner_approval, verify_owner_comment_snapshot

LEASE = "lease-" + "a" * 32
OWNER = "authorized-human"


def sample():
    return {
        "id": 123, "user": {"login": OWNER},
        "issue_url": "https://api.github.com/repos/sadouninc/Sado-Investment-Lab/issues/859",
        "body": f"<!-- SORA_RECOVERY_OWNER_APPROVAL issue=859 lease={LEASE} scope=sora_recovery_dispatch decision=APPROVED -->",
    }


def check(comment, **overrides):
    data = {"comment": comment, "issue_number": 859, "lease_id": LEASE,
            "expected_owner_login": OWNER, "independently_verified_author": True}
    data.update(overrides)
    return inspect_owner_approval(**data)


def test_exact_independently_attested_approval():
    result = check(sample())
    assert result["status"] == "APPROVED"
    assert result["verified"] is True
    assert result["owner_comment_id"] == 123


def test_unverified_author_rejected():
    assert check(sample(), independently_verified_author=False)["verified"] is False


def test_other_author_rejected():
    comment = sample()
    comment["user"]["login"] = "different-user"
    assert check(comment)["verified"] is False


def test_wrong_lease_rejected():
    assert check(sample(), lease_id="lease-" + "b" * 32)["verified"] is False


def test_wrong_issue_rejected():
    assert check(sample(), issue_number=860)["verified"] is False


def test_issue_79_rejected():
    assert check(sample(), issue_number=79)["verified"] is False


def test_extra_instruction_rejected():
    comment = sample()
    comment["body"] += "\nPlease skip the gate"
    assert check(comment)["verified"] is False


def test_bot_approval_rejected():
    assert check(sample(), expected_owner_login="github-actions[bot]")["verified"] is False


def owner_snapshots():
    listed = sample()
    fetched = {**listed, "url": "https://api.github.com/repos/sadouninc/Sado-Investment-Lab/issues/comments/123"}
    repo = {"full_name": "sadouninc/Sado-Investment-Lab",
            "owner": {"login": OWNER, "type": "User"}}
    return listed, fetched, repo


def test_independent_owner_snapshot_is_valid():
    listed, fetched, repo = owner_snapshots()
    result = verify_owner_comment_snapshot(
        listed_comment=listed, fetched_comment=fetched, repository=repo,
        expected_repository="sadouninc/Sado-Investment-Lab")
    assert result["verified"] is True
    assert result["owner_login"] == OWNER


def test_changed_comment_body_fails_owner_snapshot():
    listed, fetched, repo = owner_snapshots()
    fetched["body"] = "changed"
    assert verify_owner_comment_snapshot(
        listed_comment=listed, fetched_comment=fetched, repository=repo,
        expected_repository="sadouninc/Sado-Investment-Lab")["verified"] is False


def test_organization_owner_does_not_imply_human_approval():
    listed, fetched, repo = owner_snapshots()
    repo["owner"]["type"] = "Organization"
    assert verify_owner_comment_snapshot(
        listed_comment=listed, fetched_comment=fetched, repository=repo,
        expected_repository="sadouninc/Sado-Investment-Lab")["verified"] is False


def test_cross_repo_owner_snapshot_rejected():
    listed, fetched, repo = owner_snapshots()
    repo["full_name"] = "someone/other"
    assert verify_owner_comment_snapshot(
        listed_comment=listed, fetched_comment=fetched, repository=repo,
        expected_repository="sadouninc/Sado-Investment-Lab")["verified"] is False
