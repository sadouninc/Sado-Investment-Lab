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


def test_actual_reader_audit_logs_before_unchanged_unattested_gate():
    import io
    import json
    import textwrap
    from contextlib import redirect_stdout

    source = WORKFLOW.read_text(encoding="utf-8")
    begin = source.index('          print("CANONICAL_READER_PROJECTION="')
    end = source.index("          PY", begin)
    code = textwrap.dedent(source[begin:end])
    states = {
        "BLOCKED": "READER_HOLD_OWNER_AND_PATH_ATTESTATION_REQUIRED",
        "READY": "READER_HOLD_OWNER_AND_PATH_ATTESTATION_REQUIRED",
        "DISPATCHED": "READER_HOLD_OWNER_AND_PATH_ATTESTATION_REQUIRED",
        "ACKED": "READER_HOLD_ACTIVE_EXECUTION",
        "RUNNING": "READER_HOLD_ACTIVE_EXECUTION",
        "PR_OPEN": "READER_HOLD_ACTIVE_EXECUTION",
        "DONE": "READER_HOLD_TERMINAL", "MERGED": "READER_HOLD_TERMINAL",
        "EXPIRED": "READER_HOLD_EXPIRY_NOT_STOP_PROOF",
    }
    for state, diagnostic in states.items():
        out = io.StringIO()
        try:
            with redirect_stdout(out):
                exec(code, {"json": json, "result": {"status": state, "dispatch_allowed": False}})
        except SystemExit as exc:
            assert str(exc) == "UNEXPECTED_UNATTESTED_READER_PROJECTION"
        else:
            raise AssertionError("Unattested state escaped the existing HOLD gate")
        assert diagnostic in out.getvalue()
    out = io.StringIO()
    with redirect_stdout(out):
        exec(code, {"json": json, "result": {"status": "UNKNOWN", "reason": "PROVENANCE_UNVERIFIED",
                                             "dispatch_allowed": False}})
    assert "READER_HOLD_UNVERIFIED_PROVENANCE" in out.getvalue()


def test_b1_workflow_uses_run_owned_artifact_and_never_sets_dispatch_true():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "verify_copilot_assigned_linkage(" in source
    assert "ai-production-assigned-linkage-{run_id}" in source
    assert "COPILOT_B1_READER_AUDIT=" in source
    assert 'assert copilot_projection["dispatch_allowed"] is False' in source
    assert 'f.write("post_authorized=false' in source


def test_b1_projection_fails_closed_on_missing_duplicate_and_foreign_linkages():
    from scripts.recovery_rev2_read_bridge import project_verified_copilot_linkage_inventory

    make = lambda observed, verified, complete=True: project_verified_copilot_linkage_inventory(
        work_id="issue:859", observed_comment_ids=observed,
        verified_linkages=verified, source_complete=complete)
    valid = {"status": "ATTESTED_LINKAGE", "work_id": "issue:859",
             "comment_id": 123, "dispatch_allowed": False}
    for result in (
        make([], []), make([123], [], True), make([123], [valid], False),
        make([123, 123], [valid, valid]), make([123], [{**valid, "work_id": "issue:828"}]),
    ):
        assert result["status"] == "UNKNOWN"
        assert result["dispatch_allowed"] is False
    assert make([123], [valid])["status"] == "LINKAGE_ATTESTED"
    assert make([123], [valid])["dispatch_allowed"] is False
    protected = project_verified_copilot_linkage_inventory(
        work_id="issue:79", observed_comment_ids=[123],
        verified_linkages=[valid], source_complete=True)
    assert protected["status"] == "BLOCKED"
