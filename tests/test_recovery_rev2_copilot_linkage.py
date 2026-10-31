"""B2 Copilot linkage reader tests: fixture evidence is never production authority."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from zipfile import ZipFile

from scripts.recovery_rev2_evidence_adapter import verify_copilot_assigned_linkage

REPO = "sadouninc/Sado-Investment-Lab"
RUN = 12345
ISSUE = 859
CID = 67890
LEASE = "lease-" + "a" * 32
NOW = datetime(2026, 10, 31, 2, tzinfo=timezone.utc)


def timestamp(dt):
    return dt.isoformat().replace("+00:00", "Z")


def zipped(record, *, filename="ai-production-assigned-linkage.json", duplicate=False):
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr(filename, json.dumps(record))
        if duplicate:
            archive.writestr(filename, json.dumps(record))
    return out.getvalue()


def sample():
    record = dict(schema_version=2, comment_id=CID, writer_run_id=RUN,
                  issue_number=ISSUE, canonical_lease_id=LEASE,
                  repository=REPO, workflow_path=".github/workflows/ai-production-dispatch.yml",
                  status="ASSIGNED")
    event = dict(work_ref=f"issue:{ISSUE}", status="ASSIGNED", engine="copilot",
                 canonical_lease_id=LEASE, writer_run_id=RUN,
                 assigned_at=timestamp(NOW - timedelta(minutes=1)),
                 lease_expires_at=timestamp(NOW + timedelta(minutes=59)))
    comment = dict(id=CID,
                   issue_url=f"https://api.github.com/repos/{REPO}/issues/{ISSUE}",
                   user={"login": "github-actions[bot]"},
                   body="<!-- flow-dispatch-lease -->\n" + json.dumps(event) + "\n担当: ソラ")
    run = dict(id=RUN, name="AI Production Dispatch",
               path=".github/workflows/ai-production-dispatch.yml",
               event="workflow_dispatch", status="completed", conclusion="success",
               repository={"full_name": REPO})
    artifact = dict(name=f"ai-production-assigned-linkage-{RUN}",
                    workflow_run={"id": RUN}, expired=False,
                    expires_at=timestamp(NOW + timedelta(days=10)))
    return dict(artifact_zip=zipped(record), artifact=artifact, actions_run=run,
                comment=comment, expected_repository=REPO,
                expected_issue_number=ISSUE, now_utc=timestamp(NOW))


def check(data):
    return verify_copilot_assigned_linkage(**data)


def test_valid_linkage_is_attestation_only():
    result = check(sample())
    assert result["status"] == "ATTESTED_LINKAGE"
    assert result["dispatch_allowed"] is False
    assert result["comment_id"] == CID


def test_issue_79_hard_deny():
    data = sample()
    data["expected_issue_number"] = 79
    assert check(data)["reason"] == "PROTECTED_ISSUE_79"


def test_missing_duplicate_or_malformed_zip_fails_closed():
    data = sample()
    record = json.loads(ZipFile(BytesIO(data["artifact_zip"])).read(
        "ai-production-assigned-linkage.json"))
    for raw in (b"not-a-zip", zipped(record, filename="wrong.json"),
                zipped(record, duplicate=True), zipped(record, filename="other.json")):
        data["artifact_zip"] = raw
        assert check(data)["status"] == "UNKNOWN"


def test_artifact_run_expiry_and_name_mismatch():
    for key, value in (("expired", True), ("name", "wrong"),
                       ("workflow_run", {"id": RUN + 1}),
                       ("expires_at", timestamp(NOW - timedelta(seconds=1)))):
        data = sample()
        data["artifact"][key] = value
        assert check(data)["status"] == "UNKNOWN", key


def test_run_workflow_repository_and_status_mismatch():
    for key, value in (("path", ".github/workflows/other.yml"),
                       ("repository", {"full_name": "another/repo"}),
                       ("status", "queued"), ("conclusion", "failure"),
                       ("id", RUN + 1)):
        data = sample()
        data["actions_run"][key] = value
        assert check(data)["status"] == "UNKNOWN", key


def test_linkage_identity_mismatches():
    for key, value in (("schema_version", 1), ("comment_id", CID + 1),
                       ("writer_run_id", RUN + 1), ("issue_number", ISSUE + 1),
                       ("repository", "another/repo"),
                       ("workflow_path", "other.yml"), ("status", "ACKNOWLEDGED"),
                       ("canonical_lease_id", "owner-command")):
        data = sample()
        record = json.loads(ZipFile(BytesIO(data["artifact_zip"])).read(
            "ai-production-assigned-linkage.json"))
        record[key] = value
        data["artifact_zip"] = zipped(record)
        assert check(data)["status"] == "UNKNOWN", key


def test_comment_provenance_mismatches():
    for key, value in (("id", CID + 1),
                       ("issue_url", f"https://api.github.com/repos/{REPO}/issues/860"),
                       ("user", {"login": "untrusted"})):
        data = sample()
        data["comment"][key] = value
        assert check(data)["status"] == "UNKNOWN", key


def test_comment_event_mismatches():
    for key, value in (("work_ref", "issue:860"),
                       ("status", "ACKNOWLEDGED"), ("engine", "sora"),
                       ("canonical_lease_id", "lease-" + "b" * 32),
                       ("writer_run_id", RUN + 1),
                       ("lease_expires_at", timestamp(NOW - timedelta(seconds=1)))):
        data = sample()
        event = json.loads(data["comment"]["body"].splitlines()[1])
        event[key] = value
        data["comment"]["body"] = "<!-- flow-dispatch-lease -->\n" + json.dumps(event)
        assert check(data)["status"] == "UNKNOWN", key


def test_comment_malformed_or_duplicate_event():
    data = sample()
    data["comment"]["body"] = "<!-- flow-dispatch-lease -->\n{bad-json}"
    assert check(data)["status"] == "UNKNOWN"
    data = sample()
    data["comment"]["body"] += "\n" + data["comment"]["body"].splitlines()[1]
    assert check(data)["status"] == "UNKNOWN"


def test_missing_artifact_provenance_is_unknown():
    data = sample()
    data["artifact"].pop("workflow_run")
    assert check(data)["status"] == "UNKNOWN"
