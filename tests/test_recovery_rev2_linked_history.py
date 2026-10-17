from scripts.recovery_rev2_linked_history import project_linked_dispatch_history, matches_complete_dispatch_evidence

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


def test_complete_attested_history_required_for_stop_reconciliation():
    observed = [{"lease_id": LEASE, "writer_run_id": 123}]
    assert matches_complete_dispatch_evidence(
        observed=observed, authenticated=[dispatch()], complete=True)
    assert not matches_complete_dispatch_evidence(
        observed=observed, authenticated=[dispatch()], complete=False)


def test_self_asserted_or_missing_linkage_cannot_clear_prior_lease():
    observed = [{"lease_id": LEASE, "writer_run_id": 123}]
    assert not matches_complete_dispatch_evidence(
        observed=observed, authenticated=[dispatch(status="REPORTED_UNVERIFIED")], complete=True)
    assert not matches_complete_dispatch_evidence(
        observed=observed, authenticated=[], complete=True)
    assert not matches_complete_dispatch_evidence(
        observed=observed, authenticated=[dispatch(writer_run_id=124)], complete=True)


def test_duplicate_or_unmatched_history_never_reconciles():
    observed = [{"lease_id": LEASE, "writer_run_id": 123}] * 2
    assert not matches_complete_dispatch_evidence(
        observed=observed, authenticated=[dispatch(), dispatch()], complete=True)
    assert not matches_complete_dispatch_evidence(
        observed=[{"lease_id": LEASE, "writer_run_id": 123}],
        authenticated=[dispatch(lease_id="lease-" + "b" * 32)], complete=True)


def test_two_distinct_attested_dispatches_match_regardless_of_order():
    other = "lease-" + "b" * 32
    observed = [{"lease_id": LEASE, "writer_run_id": 123},
                {"lease_id": other, "writer_run_id": 124}]
    authenticated = [dispatch(lease_id=other, writer_run_id=124, comment_id=43), dispatch()]
    assert matches_complete_dispatch_evidence(
        observed=observed, authenticated=authenticated, complete=True)


def test_incomplete_or_malformed_stop_inventory_fails_closed():
    observed = [{"lease_id": LEASE, "writer_run_id": 123}]
    for malformed in (None, {}, "wrong", [{"lease_id": LEASE}], 
                      [{"lease_id": LEASE, "writer_run_id": True}],
                      [{"lease_id": LEASE, "writer_run_id": 0}]):
        assert not matches_complete_dispatch_evidence(
            observed=malformed, authenticated=[dispatch()], complete=True)
    assert not matches_complete_dispatch_evidence(
        observed=observed, authenticated=[dispatch()], complete=1)


def test_unverified_writer_run_or_lease_never_projects_dispatch():
    for invalid in (0, -1, "123", False):
        result = project([dispatch(writer_run_id=invalid)])
        assert result["status"] == "UNKNOWN"
        assert result["dispatch_allowed"] is False
    for invalid in (None, 17, False):
        result = project([dispatch(lease_id=invalid)])
        assert result["status"] == "UNKNOWN"
        assert result["dispatch_allowed"] is False


def test_unverified_history_cannot_be_used_as_retry_permission():
    for items in ([dispatch(dispatch_allowed=True)],
                  [dispatch(status="UNKNOWN")],
                  [dispatch(comment_id=0)]):
        result = project(items)
        assert result["status"] == "UNKNOWN"
        assert result["dispatch_allowed"] is False


def test_noncanonical_lease_rejected_by_projection_and_reconciliation():
    observed = [{"lease_id": LEASE, "writer_run_id": 123}]
    for invalid in ("", "lease-wrong", "lease-" + "A" * 32, "lease-" + "0" * 31):
        assert project([dispatch(lease_id=invalid)])["status"] == "UNKNOWN"
        assert not matches_complete_dispatch_evidence(
            observed=[{"lease_id": invalid, "writer_run_id": 123}],
            authenticated=[dispatch(lease_id=invalid)], complete=True)
        assert not matches_complete_dispatch_evidence(
            observed=observed, authenticated=[dispatch(lease_id=invalid)], complete=True)
