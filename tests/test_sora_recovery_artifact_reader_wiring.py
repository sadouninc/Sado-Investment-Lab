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


def test_artifact_reader_audit_exposes_reconciliation_without_authorizing_post():
    source = WORKFLOW.read_text(encoding="utf-8")
    for field in (
        "ARTIFACT_READER_AUDIT=",
        '"observed_count": len(observed_dispatches)',
        '"authenticated_count": len(linked_dispatches)',
        '"inventory_complete": all_dispatches_linked and bool(linked_dispatches)',
        '"reader_status": linked_projection.get("status")',
        '"dispatch_allowed": linked_projection.get("dispatch_allowed")',
    ):
        assert field in source
    assert 'assert linked_projection.get("dispatch_allowed") is False' in source
    assert 'f.write("post_authorized=false' in source


def test_github_actions_summary_uses_real_newline_escapes():
    """An escaped backslash-n collapses Markdown into one line."""
    import ast
    source = WORKFLOW.read_text(encoding="utf-8")
    lines = [line.strip() for line in source.splitlines()
             if line.strip().startswith("summary.write(")]
    assert len(lines) == 8
    assert all("\\\\n" not in line for line in lines)
    # Evaluate the literal heading/table header and require actual line breaks.
    heading = ast.literal_eval(lines[0].removeprefix("summary.write(").removesuffix(")"))
    header = ast.literal_eval(lines[1].removeprefix("summary.write(").removesuffix(")"))
    assert heading.endswith("\n\n")
    assert header == "| Evidence | Value |\n|---|---|\n"
    assert all(r"\n" in line for line in lines)


def test_github_output_writes_single_newline_delimited_hold_value():
    import ast
    source = WORKFLOW.read_text(encoding="utf-8")
    lines = [line.strip() for line in source.splitlines()
             if line.strip().startswith('f.write("post_authorized=')]
    assert len(lines) == 1
    assert "\\\\n" not in lines[0]
    output = ast.literal_eval(lines[0].removeprefix("f.write(").removesuffix(")"))
    assert output == "post_authorized=false\n"


def test_owner_inventory_runtime_missing_source_stays_unknown_and_hold_only():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "project_attested_owner_inventory(" in source
    assert "work_id=work_id, claims=None, source_refs=None" in source
    assert 'assert owner_inventory["dispatch_allowed"] is False' in source
    assert "OWNER_INVENTORY_AUDIT=" in source
    assert "evidence_complete=False" in source
    assert 'f.write("post_authorized=false' in source
