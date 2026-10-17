from scripts.recovery_rev2_linked_history import project_linked_dispatch_history

LEASE = "lease-" + "a" * 32

def dispatch(**overrides):
    value = {"status": "ATTESTED_LINKAGE", "work_id": "issue:859",
             "comment_id": 42, "lease_id": LEASE, "writer_run_id": 123, "dispatch_allowed": False}
    value.update(overrides)
    return value

def project(items, complete=True):
    return project_linked_dispatch_history(
        work_id="issue:859", linked_dispatches=items, complete_history=complete)

def test_verified_single_legacy_dispatch_projects_hold():
    result = project([dispatch()])
    assert result["status"] == "DISPATCHED"
    assert result["attempt"] == 1
    assert result["prior_dispatch_count"] == 1
    assert result["dispatch_allowed"] is False

def test_unverified_linkage_is_never_migrated():
    assert project([dispatch(status="REPORTED_UNVERIFIED")])["status"] == "UNKNOWN"

def test_multiple_legacy_dispatches_require_expiry_proof():
    result = project([dispatch(), dispatch(comment_id=43, lease_id="lease-" + "b"*32)])
    assert result["reason"] == "LEGACY_RETRY_TRANSITIONS_UNVERIFIED"

def test_incomplete_history_never_projects_ready():
    assert project([], complete=False)["status"] == "UNKNOWN"

def test_attested_empty_history_stays_read_only():
    result = project([])
    assert result["status"] == "READY"
    assert result["dispatch_allowed"] is False

def test_cross_issue_linkage_rejected():
    assert project([dispatch(work_id="issue:860")])["status"] == "UNKNOWN"

def test_missing_lease_not_migrated():
    assert project([dispatch(lease_id=None)])["status"] == "UNKNOWN"

def test_protected_issue_stays_denied():
    result = project_linked_dispatch_history(
        work_id="issue:79", linked_dispatches=[], complete_history=True)
    assert result["status"] == "BLOCKED"


def test_missing_writer_run_cannot_be_promoted():
    result = project([dispatch(writer_run_id=None)])
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "MISSING_LINKED_WRITER_RUN"


def test_boolean_writer_run_id_is_rejected():
    result = project([dispatch(writer_run_id=True)])
    assert result["status"] == "UNKNOWN"
    assert result["dispatch_allowed"] is False
