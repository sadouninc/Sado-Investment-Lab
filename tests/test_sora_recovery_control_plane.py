from pathlib import Path

WORKFLOW=Path(".github/workflows/sora-recovery-control-plane.yml")

def text():
    return WORKFLOW.read_text(encoding="utf-8")

def test_sora_recovery_control_plane_is_external_writer_backed():
    t=text()
    assert "issues: write" in t
    assert "scheduled_pull" in t
    assert "executor=SORA" in t
    assert "status:\"DISPATCHED\"" in t

def test_issue_79_is_hard_denied():
    t=text()
    assert '[[ "$issue" != "79" ]]' in t
    assert '[[ "$ISSUE" != "79" ]]' in t

def test_sora_lease_is_idempotent_and_attributable():
    t=text()
    assert "SORA_LEASE_ALREADY_PERSISTED" in t
    assert "GITHUB_RUN_ID" in t
    assert "AUTO_ROUTER_DISPATCH" in t

def test_scheduled_pull_can_discover_recovery_without_chatgpt_write():
    t=text()
    assert 'cron: "13,43 * * * *"' in t
    assert "gh api --paginate" in t
    assert "per_page=100" in t
    assert "jq -s 'add // []'" in t
    assert 'test("(?m)^## Recovery Work Contract' in t
    assert 'Flow Authority:' in t
    assert 'Recovery Engineer:' in t
    assert 'P[01]' in t
    assert 'contains("## Recovery Work Contract")' not in t

def test_prior_dispatch_requires_canonical_reconciliation():
    """Expiry alone must never authorize another SORA lease."""
    t = text()
    assert "PRIOR_SORA_DISPATCH_REQUIRES_CANONICAL_RECONCILIATION" in t
    assert 'test("AUTO_ROUTER_DISPATCH")' in t
    assert 'test("executor=SORA")' in t
    assert 'test("target_issue=" + $issue + "([^0-9]|$)")' in t
    assert "expiry_epoch > now" not in t
    assert "INVALID_RECOVERY_CONTRACT" in t
    assert "jq -s 'add // []'" in t


def test_lease_event_extraction_behavior():
    """Exercise the exact jq extraction shape against a real multiline comment."""
    import json
    import shutil
    import subprocess
    import pytest

    if not shutil.which("jq"):
        pytest.skip("jq is required for the workflow parser")
    event = {"canonical_lease_id": "lease-" + "a" * 32,
             "lease_expires_at": "2030-01-01T00:00:00Z", "status": "DISPATCHED"}
    comment = ("<!-- AUTO_ROUTER_DISPATCH lease_id=" + event["canonical_lease_id"]
               + " executor=SORA target_issue=859 -->\n"
               + json.dumps(event) + "\n\n担当: ナギ")
    jq_program = 'split("\n") | map(select(startswith("{") and contains("lease_expires_at"))) | first // empty'
    extracted = subprocess.run(
        ["jq", "-Rrs", jq_program], input=comment + "\n",
        text=True, capture_output=True, check=True
    ).stdout.strip()
    assert json.loads(extracted) == event
    parsed = subprocess.run(
        ["jq", "-er", ".lease_expires_at | strings"],
        input=extracted + "\n", text=True, capture_output=True, check=True
    )
    assert parsed.stdout.strip() == event["lease_expires_at"]


def test_recovery_contract_is_checked_for_dispatch_and_scheduled_pull():
    t = text()
    assert t.count('test("(?m)^## Recovery Work Contract') == 2
    assert t.count('Flow Authority:') >= 2
    assert t.count('Recovery Engineer:') >= 2

def test_lease_expiry_cases_with_actual_jq_and_date():
    """Active, expired and malformed expiry cases using the workflow's tools."""
    import json
    import shutil
    import subprocess
    import pytest

    if not all(shutil.which(command) for command in ("jq", "date")):
        pytest.skip("jq and GNU date are required")
    cases = [
        ("2999-01-01T00:00:00Z", "active"),
        ("2000-01-01T00:00:00Z", "expired"),
        ("not-a-timestamp", "ambiguous"),
    ]
    for expiry, expected in cases:
        event = json.dumps({"lease_expires_at": expiry})
        result = subprocess.run(
            ["jq", "-er", ".lease_expires_at | strings"],
            input=event, text=True, capture_output=True, check=True,
        )
        epoch = subprocess.run(
            ["date", "-u", "-d", result.stdout.strip(), "+%s"],
            text=True, capture_output=True,
        )
        if epoch.returncode != 0:
            outcome = "ambiguous"
        else:
            now = int(subprocess.check_output(["date", "-u", "+%s"], text=True))
            outcome = "active" if int(epoch.stdout.strip()) > now else "expired"
        assert outcome == expected


def test_scheduled_priority_is_explicit_and_deterministic():
    """P0 must precede a newer P1; tie-break is issue number, not update time."""
    t = text()
    assert 'sort_by((if (.body | test(' in t
    assert 'Priority:' in t
    assert 'then 0 else 1 end), .number)' in t
    assert '| first | .number // empty' in t


def test_scheduled_priority_does_not_select_protected_issue():
    t = text()
    assert '.number != 79' in t
    assert '[[ "$issue" != "79" ]]' in t
