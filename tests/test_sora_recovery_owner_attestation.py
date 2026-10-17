from scripts.sora_recovery_owner_attestation import inspect_owner_approval

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
