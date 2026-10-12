"""#859 integration-contract probes. Fixtures are synthesized from PR #860's
HEAD workflow event fields; they are not production GitHub evidence.
"""
import json
from datetime import datetime, timedelta, timezone

from scripts.sora_recovery_pickup import discover_sora_pickup, verify_sora_pickup_provenance

NOW = datetime(2026, 10, 12, 8, 2, tzinfo=timezone.utc)
ISSUE = 859
LEASE = "lease-" + "b" * 32
MARKER = f"<!-- AUTO_ROUTER_DISPATCH lease_id={LEASE} executor=SORA target_issue={ISSUE} -->"


def comment(*, with_writer_run_id=False):
    # Mirrors the JSON event fields built by PR #860 workflow (no writer_run_id).
    event = dict(work_ref="issue:859", owner_slice="issue-859", executor="SORA",
                 canonical_lease_id=LEASE,
                 assigned_at="2026-10-12T08:00:00Z",
                 lease_expires_at="2026-10-12T09:30:00Z",
                 status="DISPATCHED", source="scheduled_pull")
    if with_writer_run_id:
        event["writer_run_id"] = 38000000000
    return {"id": 6038000000, "user": {"login": "github-actions[bot]"},
            "body": MARKER + "\n" + json.dumps(event) + "\n\n担当: 🌊ナギ"}


def test_current_pr860_event_cannot_be_picked_up_by_readonly_consumer():
    assert discover_sora_pickup(issue_number=ISSUE, comments=[comment()], now=NOW)["status"] == "EVIDENCE_UNVERIFIED"


def test_schema_alignment_creates_only_a_candidate_not_execution_authority():
    result = discover_sora_pickup(issue_number=ISSUE, comments=[comment(with_writer_run_id=True)], now=NOW)
    assert result["status"] == "PICKUP_CANDIDATE"
    assert result["write_performed"] is False
    assert result["required_next_gate"] == "VERIFY_WRITER_RUN_AND_FRESH_AUTHORITY"
    assert result["candidate"]["comment_id"] == 6038000000


def test_successful_run_metadata_still_does_not_authorize_execution():
    candidate = discover_sora_pickup(issue_number=ISSUE, comments=[comment(with_writer_run_id=True)], now=NOW)["candidate"]
    writer_run = dict(id=38000000000, event="schedule", status="completed",
                      conclusion="success", head_branch="main",
                      path=".github/workflows/sora-recovery-control-plane.yml@main",
                      repository={"full_name": "sadouninc/Sado-Investment-Lab"},
                      created_at="2026-10-12T07:58:00Z")
    issue = dict(number=859, state="open", pull_request=None,
                 body="## Recovery Work Contract — NAGI → SORA\n"
                      "**Priority:** P0 Flow Recovery\n"
                      "**Flow Authority:** 🌊ナギ remains Single Flow Authority\n"
                      "**Recovery Engineer:** 🪐ソラ\n")
    result = verify_sora_pickup_provenance(candidate=candidate, writer_run=writer_run,
            issue=issue, repository_full_name="sadouninc/Sado-Investment-Lab", now=NOW)
    assert result["status"] == "RUN_METADATA_CONSISTENT_READ_ONLY"
    assert result["execution_authorized"] is False
    assert result["required_next_gate"] == "ATTEST_COMMENT_RUN_BINDING_AND_FRESH_AUTHORITY"


def test_expired_candidate_cannot_activate_even_with_writer_id():
    assert discover_sora_pickup(issue_number=ISSUE,
            comments=[comment(with_writer_run_id=True)], now=NOW + timedelta(hours=2))["status"] == "LEASE_EXPIRED"


def test_protected_issue_is_never_scanned_for_pickup():
    assert discover_sora_pickup(issue_number=79, comments=[], now=NOW)["status"] == "PROTECTED_ISSUE"
