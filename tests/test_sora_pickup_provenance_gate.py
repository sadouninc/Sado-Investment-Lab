"""Provenance gate tests for existing #859 read-only pickup candidate.

The writer workflow is not deployed; this verifies supplied GitHub API snapshots,
not a production execution or permission to mutate GitHub.
"""
from datetime import datetime, timedelta, timezone
import pytest
from scripts.sora_recovery_pickup import verify_sora_pickup_provenance

NOW = datetime(2026, 10, 12, 7, 38, tzinfo=timezone.utc)
ASSIGNED = (NOW - timedelta(minutes=5)).isoformat()
EXPIRES = (NOW + timedelta(minutes=85)).isoformat()


def candidate(**overrides):
    obj = dict(lease_id='lease-'+'a'*32, target_issue=859, comment_id=123,
               writer_run_id=37010001, assigned_at=ASSIGNED,
               lease_expires_at=EXPIRES, source='scheduled_pull')
    obj.update(overrides)
    return obj


def run(**overrides):
    obj = dict(id=37010001, event='schedule', status='completed',
               conclusion='success', head_branch='main',
               path='.github/workflows/sora-recovery-control-plane.yml@main',
               repository={'full_name':'sadouninc/Sado-Investment-Lab'},
               created_at='2026-10-12T07:30:00Z')
    obj.update(overrides)
    return obj


def issue(**overrides):
    obj = dict(number=859, state='open', pull_request=None,
               body='## Recovery Work Contract — NAGI → SORA\n'
                    '**Priority:** P0 Flow Recovery\n'
                    '**Flow Authority:** 🌊ナギ remains Single Flow Authority\n'
                    '**Recovery Engineer:** 🪐ソラ\n')
    obj.update(overrides)
    return obj


def verify(c=None, r=None, i=None):
    return verify_sora_pickup_provenance(
        candidate=c if c is not None else candidate(),
        writer_run=r if r is not None else run(),
        issue=i if i is not None else issue(),
        repository_full_name='sadouninc/Sado-Investment-Lab', now=NOW)


def test_happy_path_is_read_only_not_authorization():
    result=verify()
    assert result['status']=='RUN_METADATA_CONSISTENT_READ_ONLY'
    assert result['write_performed'] is False
    assert result['execution_authorized'] is False
    assert result['required_next_gate']=='ATTEST_COMMENT_RUN_BINDING_AND_FRESH_AUTHORITY'

@pytest.mark.parametrize('bad', [
    {'id':37010002}, {'event':'workflow_dispatch'},
    {'status':'in_progress'}, {'conclusion':'failure'},
    {'head_branch':'feature'},
    {'path':'.github/workflows/other.yml@main'},
    {'repository':{'full_name':'attacker/fork'}},
    {'created_at':'2026-10-12T07:40:00Z'},
])
def test_wrong_writer_run_fails_closed(bad):
    assert verify(r=run(**bad))['status']=='EVIDENCE_UNVERIFIED'

@pytest.mark.parametrize('bad', [
    {'state':'closed'}, {'number':860}, {'pull_request':{}},
    {'body':'## Recovery Work Contract — NAGI → SORA\n**Priority:** P0\n**Flow Authority:** other\n**Recovery Engineer:** 🪐ソラ'},
])
def test_invalid_fresh_issue_fails_closed(bad):
    assert verify(i=issue(**bad))['status']=='EVIDENCE_UNVERIFIED'


def test_expired_lease_fails_closed():
    assert verify(c=candidate(lease_expires_at=(NOW-timedelta(seconds=1)).isoformat()))['status']=='LEASE_EXPIRED'


def test_protected_issue_fails_closed_without_any_mutation():
    assert verify(c=candidate(target_issue=79))['status']=='PROTECTED_ISSUE'


def test_dispatch_requires_dispatch_event():
    assert verify(c=candidate(source='workflow_dispatch'))['status']=='EVIDENCE_UNVERIFIED'
    assert verify(c=candidate(source='workflow_dispatch'),r=run(event='workflow_dispatch'))['status']=='RUN_METADATA_CONSISTENT_READ_ONLY'


def test_bad_timestamp_fails_closed():
    assert verify(c=candidate(assigned_at='nonsense'))['status']=='EVIDENCE_UNVERIFIED'


def test_lease_must_have_nonblank_marker_identity():
    assert verify(c=candidate(lease_id='wrong'))['status']=='EVIDENCE_UNVERIFIED'
