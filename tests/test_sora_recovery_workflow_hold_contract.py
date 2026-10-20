"""Regression contract for the deployed #859 HOLD-only Recovery workflow.

These tests intentionally do not authorize production dispatch.
"""
from pathlib import Path
import re


WORKFLOW = Path(".github/workflows/sora-recovery-control-plane.yml")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_unverified_reader_provenance_remains_hold_only():
    source = _workflow()
    assert 'provenance_verified=False' in source
    assert 'trusted_comment_ids=set()' in source
    assert 'READER_HOLD_UNVERIFIED_PROVENANCE' in source
    assert 'UNAUTHORIZED_READER_DISPATCH' in source


def test_deployed_gate_requires_complete_evidence_before_post():
    source = _workflow()
    assert re.search(r"decide_dispatch\([\s\S]*?evidence_complete=False\)", source)
    assert 'if decision.get("post_authorized") is not False:' in source
    assert 'raise SystemExit("UNAUTHORIZED_DISPATCH_GATE")' in source
    assert 'f.write("post_authorized=false\\n")' in source


def test_mutating_steps_depend_on_positive_guard_output():
    source = _workflow()
    assert 'name: Persist idempotent SORA recovery lease' in source
    assert "steps.guard.outputs.post_authorized == 'true'" in source
    assert '[[ "$ISSUE" != "79" ]] || exit 79' in source


def test_dispatch_gate_never_uses_reader_as_authority():
    from scripts.sora_recovery_dispatch_gate import decide_dispatch

    result = decide_dispatch(
        issue_number=859,
        lease_id="lease-" + "a" * 32,
        candidate={"status": "ALLOW_PRELIMINARY", "issue_number": 859},
        projection={"status": "UNKNOWN", "dispatch_allowed": False},
        owner_gate={"status": "UNKNOWN", "verified": False},
        evidence_complete=False,
    )
    assert result["status"] == "HOLD"
    assert result["reason"] == "INCOMPLETE_EVIDENCE"
    assert result["post_authorized"] is False
