"""Static workflow contract: authenticated artifact inventory feeds read-only Reader.

The workflow remains intentionally hold-only until separate Owner authorization.
"""
from pathlib import Path

WORKFLOW = Path(".github/workflows/sora-recovery-control-plane.yml")


def test_workflow_projects_authenticated_artifact_inventory():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "project_authenticated_artifact_inventory(" in source
    assert "authenticated=linked_dispatches" in source
    assert "observed=observed_dispatches" in source
    assert "complete=all_dispatches_linked and bool(linked_dispatches)" in source


def test_workflow_never_promotes_observation_to_dispatch_authority():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "evidence_complete=False" in source
    assert "post_authorized=false" in source
    assert "steps.guard.outputs.post_authorized == 'true'" in source
    assert '[[ "$ISSUE" != "79" ]] || exit 79' in source
