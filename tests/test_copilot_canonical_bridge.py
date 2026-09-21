from pathlib import Path

WORKFLOW=Path('.github/workflows/ai-production-dispatch.yml')
ROUTER=Path('scripts/multi_executor_router.py')

def test_copilot_is_canonical_executor_after_free_providers():
    text=ROUTER.read_text(encoding='utf-8')
    assert 'DEFAULT_EXECUTOR_ORDER = ("AMAZON_Q", "JULES", "COPILOT", "SORA")' in text

def test_existing_production_workflow_accepts_canonical_lease_ingress():
    text=WORKFLOW.read_text(encoding='utf-8')
    assert 'workflow_dispatch:' in text
    assert 'lease_id:' in text
    assert 'CANONICAL_LEASE_ACCEPTED' in text
    assert 'CANONICAL_LEASE_EVIDENCE_MISSING' in text
    assert 'executor=COPILOT' in text

def test_canonical_ingress_keeps_hard_deny_and_owner_command_path():
    text=WORKFLOW.read_text(encoding='utf-8')
    assert 'PROTECTED_ISSUE_79' in text
    assert "[[ \"$normalized\" == '/ai copilot' ]]" in text
    assert 'github.event.comment.user.login == github.repository_owner' in text

def test_canonical_ingress_validates_lease_shape_fail_closed():
    text=WORKFLOW.read_text(encoding='utf-8')
    assert 'INVALID_ROUTED_LEASE' in text
    assert '^lease-[0-9a-f]{32}$' in text
