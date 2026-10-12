import json
from datetime import datetime, timedelta, timezone
import pytest
from scripts.sora_recovery_pickup import discover_sora_pickup

NOW = datetime(2026, 10, 12, 5, 58, tzinfo=timezone.utc)
LEASE = "lease-" + "a" * 32
MARKER = f"<!-- AUTO_ROUTER_DISPATCH lease_id={LEASE} executor=SORA target_issue=859 -->"

def event(**kw):
    data = dict(work_ref="issue:859", owner_slice="issue-859", executor="SORA",
                canonical_lease_id=LEASE, status="DISPATCHED", source="scheduled_pull",
                writer_run_id=37010001,
                assigned_at=(NOW - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                lease_expires_at=(NOW + timedelta(minutes=80)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    data.update(kw)
    return data

def comment(*, data=None, body=None, **kw):
    obj = dict(id=123456, user={"login": "github-actions[bot]"},
               body=MARKER + "\n" + json.dumps(event() if data is None else data) + "\n\n担当: 🌊ナギ")
    if body is not None: obj["body"] = body
    obj.update(kw)
    return obj

def pickup(*comments, issue=859):
    return discover_sora_pickup(issue_number=issue, comments=comments, now=NOW)

def test_valid_lease_is_candidate_not_authorization():
    r=pickup(comment())
    assert r["status"] == "PICKUP_CANDIDATE" and r["write_performed"] is False
    assert r["required_next_gate"] == "VERIFY_WRITER_RUN_AND_FRESH_AUTHORITY"
    assert r["candidate"]["writer_run_id"] == 37010001

def test_no_lease():
    assert pickup()["status"] == "NO_LEASE"

def test_quoted_marker_not_actionable():
    assert pickup(comment(body="Historical example:\n> " + MARKER))["status"] == "NO_LEASE"

def test_untrusted_author_fails_closed():
    assert pickup(comment(user={"login":"someone"}))["status"] == "EVIDENCE_UNVERIFIED"

def test_missing_run_id_fails_closed_for_current_pr860_schema():
    data=event(); data.pop("writer_run_id")
    assert pickup(comment(data=data))["status"] == "EVIDENCE_UNVERIFIED"

def test_mismatched_issue_and_lease_fails_closed():
    assert pickup(comment(data=event(work_ref="issue:900")))["status"] == "EVIDENCE_UNVERIFIED"
    assert pickup(comment(data=event(canonical_lease_id="lease-" + "b"*32)))["status"] == "EVIDENCE_UNVERIFIED"

def test_invalid_expiry_and_future_assignment_fail_closed():
    assert pickup(comment(data=event(lease_expires_at="nonsense")))["status"] == "EVIDENCE_UNVERIFIED"
    future=(NOW+timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert pickup(comment(data=event(assigned_at=future)))["status"] == "EVIDENCE_UNVERIFIED"

def test_expired_lease_is_not_claimed():
    past=(NOW-timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert pickup(comment(data=event(lease_expires_at=past)))["status"] == "LEASE_EXPIRED"

def test_multiple_active_leases_are_ambiguous():
    b="lease-"+"b"*32
    second=comment(data=event(canonical_lease_id=b),id=222222)
    second["body"]=f"<!-- AUTO_ROUTER_DISPATCH lease_id={b} executor=SORA target_issue=859 -->\n"+json.dumps(event(canonical_lease_id=b))
    assert pickup(comment(),second)["status"] == "AMBIGUOUS_ACTIVE_LEASE"

def test_expired_plus_active_selects_only_active():
    past=(NOW-timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r=pickup(comment(data=event(lease_expires_at=past),id=100),comment(id=101))
    assert r["status"] == "PICKUP_CANDIDATE" and r["candidate"]["comment_id"]==101

def test_protected_issue_79_never_inspected_or_claimed():
    assert pickup(comment(),issue=79)["status"] == "PROTECTED_ISSUE"

def test_missing_comment_id_fails_closed():
    assert pickup(comment(id=None))["status"] == "EVIDENCE_UNVERIFIED"

def test_invalid_window_longer_than_90_minutes_fails_closed():
    long=(NOW+timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert pickup(comment(data=event(lease_expires_at=long)))["status"] == "EVIDENCE_UNVERIFIED"

def test_wrong_target_issue_ignored():
    assert pickup(comment(),issue=900)["status"] == "NO_LEASE"

def test_non_utc_timestamp_fails_closed():
    assert pickup(comment(data=event(assigned_at="2026-10-12T05:48:00+00:00")))["status"] == "EVIDENCE_UNVERIFIED"


def test_writer_two_date_calls_one_second_skew_is_tolerated():
    # The PR workflow computes assigned_at and lease_expires_at in separate calls.
    skewed=(NOW+timedelta(minutes=80,seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert pickup(comment(data=event(lease_expires_at=skewed)))["status"] == "PICKUP_CANDIDATE"
