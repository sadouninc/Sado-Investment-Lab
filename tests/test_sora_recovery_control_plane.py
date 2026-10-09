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
    assert 'contains("## Recovery Work Contract")' in t

def test_lease_event_reader_uses_real_newlines():
    """Regression: a literal backslash-n makes a valid JSON event invisible."""
    t = text()
    assert "printf '%s\\n' \"$body\"" in t
    assert "split(\"\\n\")" in t
    assert "printf '%s\\\\n' \"$body\"" not in t
    assert "split(\"\\\\n\")" not in t


def test_active_and_ambiguous_lease_fail_closed():
    t = text()
    assert "ACTIVE_SORA_LEASE_EXISTS" in t
    assert "AMBIGUOUS_PRIOR_LEASE" in t
    assert "expiry_epoch > now" in t
    assert "INVALID_RECOVERY_CONTRACT" in t
    assert "jq -s 'add // []'" in t
