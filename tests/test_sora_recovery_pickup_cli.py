"""Regression coverage for the read-only recovery inspection adapter."""
import json
from datetime import datetime, timedelta, timezone
from scripts.sora_recovery_pickup_cli import inspect_snapshot, main

NOW = datetime(2026, 10, 12, 8, 58, tzinfo=timezone.utc)
LEASE = 'lease-' + 'c' * 32
MARKER = f'<!-- AUTO_ROUTER_DISPATCH lease_id={LEASE} executor=SORA target_issue=859 -->'
ISSUE = {'number':859, 'state':'open', 'pull_request':None, 'comments':1,
         'body':'## Recovery Work Contract — NAGI → SORA\n**Priority:** P0 Flow Recovery\n**Flow Authority:** 🌊ナギ\n**Recovery Engineer:** 🪐ソラ\n'}
EVENT = {'work_ref':'issue:859','owner_slice':'issue-859','executor':'SORA',
         'canonical_lease_id':LEASE,'status':'DISPATCHED','source':'scheduled_pull',
         'writer_run_id':30001,
         'assigned_at':(NOW-timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
         'lease_expires_at':(NOW+timedelta(minutes=80)).strftime('%Y-%m-%dT%H:%M:%SZ')}
COMMENTS = [{'id':22222,'user':{'login':'github-actions[bot]'},
             'body':MARKER+'\n'+json.dumps(EVENT)+'\n'}]
RUN = {'id':30001,'event':'schedule','status':'completed','conclusion':'success',
       'head_branch':'main','path':'.github/workflows/sora-recovery-control-plane.yml@main',
       'repository':{'full_name':'sadouninc/Sado-Investment-Lab'},
       'created_at':(NOW-timedelta(minutes=12)).strftime('%Y-%m-%dT%H:%M:%SZ')}

def inspect(issue=ISSUE,comments=COMMENTS,writer_run=RUN):
    return inspect_snapshot(issue=issue,comments=comments,writer_run=writer_run,
                            repository='sadouninc/Sado-Investment-Lab',now=NOW)

def test_consistent_run_never_authorizes_execution():
    r=inspect()
    assert r['status']=='RUN_METADATA_CONSISTENT_READ_ONLY'
    assert r['execution_authorized'] is False and r['write_performed'] is False
    assert r['required_next_gate']=='ATTEST_COMMENT_RUN_BINDING_AND_FRESH_AUTHORITY'

def test_missing_writer_run_is_not_a_pickup():
    assert inspect(writer_run=None)['status']=='WRITER_RUN_EVIDENCE_MISSING'

def test_current_pr860_missing_writer_id_is_unverified():
    event={k:v for k,v in EVENT.items() if k!='writer_run_id'}
    comment={**COMMENTS[0],'body':MARKER+'\n'+json.dumps(event)}
    assert inspect(comments=[comment])['status']=='EVIDENCE_UNVERIFIED'

def test_protected_issue_never_inspected():
    assert inspect(issue={**ISSUE,'number':79})['status']=='PROTECTED_ISSUE'

def test_expired_lease_is_not_claimed():
    assert inspect_snapshot(issue=ISSUE,comments=COMMENTS,writer_run=RUN,
                            repository='sadouninc/Sado-Investment-Lab',
                            now=NOW+timedelta(hours=2))['status']=='LEASE_EXPIRED'

def test_wrong_run_metadata_is_unverified():
    assert inspect(writer_run={**RUN,'repository':{'full_name':'another/repo'}})['status']=='EVIDENCE_UNVERIFIED'

def test_missing_or_malformed_snapshot_fails_closed():
    assert inspect(issue={},comments=[])['status']=='EVIDENCE_UNVERIFIED'
    assert inspect(comments=[None])['status']=='EVIDENCE_UNVERIFIED'

def test_cli_json_snapshot_roundtrip(tmp_path,capsys):
    paths=[]
    for name,obj in [('issue',ISSUE),('comments',COMMENTS),('run',RUN)]:
        p=tmp_path/(name+'.json');p.write_text(json.dumps(obj));paths.append(str(p))
    rc=main(['--issue',paths[0],'--comments',paths[1],'--writer-run',paths[2],
             '--repository','sadouninc/Sado-Investment-Lab','--now',NOW.isoformat()])
    result=json.loads(capsys.readouterr().out)
    assert rc==0 and result['execution_authorized'] is False

def test_cli_unreadable_input_fails_closed(tmp_path,capsys):
    rc=main(['--issue',str(tmp_path/'absent.json'),'--comments',str(tmp_path/'absent2.json'),
             '--repository','sadouninc/Sado-Investment-Lab'])
    result=json.loads(capsys.readouterr().out)
    assert rc==2 and result['status']=='EVIDENCE_UNVERIFIED'


def test_closed_issue_never_reports_pickup_even_with_valid_lease():
    assert inspect(issue={**ISSUE, 'state': 'closed'})['status'] == 'TARGET_NOT_OPEN'
    assert inspect(issue={**ISSUE, 'state': 'closed'}, comments=[])['status'] == 'TARGET_NOT_OPEN'


def test_pr_target_never_reports_pickup():
    assert inspect(issue={**ISSUE, 'pull_request': {'url': 'https://example.invalid'}})['status'] == 'TARGET_NOT_OPEN'


def test_non_recovery_contract_never_reports_pickup():
    assert inspect(issue={**ISSUE, 'body': 'Regular issue'})['status'] == 'RECOVERY_CONTRACT_UNVERIFIED'
    assert inspect(issue={**ISSUE, 'body': None}, comments=[])['status'] == 'RECOVERY_CONTRACT_UNVERIFIED'


def test_unmodified_open_recovery_contract_still_remains_read_only():
    result = inspect()
    assert result['status'] == 'RUN_METADATA_CONSISTENT_READ_ONLY'
    assert result['execution_authorized'] is False


def test_comment_snapshot_truncated_blocks_before_pickup():
    result = inspect(comments=[])
    assert result['status'] == 'COMMENT_SNAPSHOT_UNVERIFIED'
    assert result['reason'] == 'COMMENT_COUNT_MISMATCH'
    assert result['expected'] == 1 and result['observed'] == 0
    assert result['execution_authorized'] is False


def test_comment_snapshot_extra_rows_or_stale_count_blocks():
    result = inspect(issue={**ISSUE, 'comments':0})
    assert result['status'] == 'COMMENT_SNAPSHOT_UNVERIFIED'
    assert result['reason'] == 'COMMENT_COUNT_MISMATCH'


def test_comment_count_missing_or_boolean_blocks():
    for issue in ({k:v for k,v in ISSUE.items() if k != 'comments'},
                  {**ISSUE, 'comments':True},
                  {**ISSUE, 'comments':-1}):
        result = inspect(issue=issue)
        assert result['status'] == 'COMMENT_SNAPSHOT_UNVERIFIED'
        assert result['reason'] == 'COMMENT_COUNT_MISSING'
        assert result['execution_authorized'] is False


def test_complete_empty_comment_snapshot_reports_no_lease():
    result = inspect(issue={**ISSUE, 'comments':0}, comments=[])
    assert result['status'] == 'NO_LEASE'
    assert result['execution_authorized'] is False
