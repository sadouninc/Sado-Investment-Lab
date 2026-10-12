"""Pure Rev.2 identity and ACK validation regressions."""
import pytest
from scripts.recovery_rev2_identity import lease_id, ack_schema

WORK = "issue:859"

def test_deterministic_lease():
    assert lease_id(WORK, 123, 1) == lease_id(WORK, 123, 1)
    assert lease_id(WORK, 123, 1) != lease_id(WORK, 123, 2)
    assert lease_id(WORK, 123, 1) != lease_id(WORK, 124, 1)

@pytest.mark.parametrize("work,run,attempt", [
    ("issue:79", 123, 1), ("issue:0", 123, 1), ("#859", 123, 1),
    (WORK, 0, 1), (WORK, True, 1), (WORK, 123, 0), (WORK, 123, 5),
])
def test_invalid_lease_identity(work, run, attempt):
    with pytest.raises(ValueError):
        lease_id(work, run, attempt)

def test_ack_structure_is_not_provenance():
    lid = lease_id(WORK, 123, 1)
    ack = dict(lease_id=lid, work_id=WORK, executor="SORA",
               run_id=456, timestamp="2026-10-12T10:00:00Z", status="ACKNOWLEDGED")
    result = ack_schema(ack, work_id=WORK, lease=lid, executor="SORA")
    assert result == {"status": "ACK_SCHEMA_VALID_UNVERIFIED", "provenance_verified": False}

def test_ack_wrong_lease_fails_closed():
    lid = lease_id(WORK, 123, 1)
    ack = dict(lease_id=lease_id(WORK, 123, 2), work_id=WORK, executor="SORA",
               run_id=456, timestamp="2026-10-12T10:00:00Z", status="ACKNOWLEDGED")
    assert ack_schema(ack, work_id=WORK, lease=lid, executor="SORA")["status"] == "UNKNOWN"

def test_ack_missing_run_fails_closed():
    lid = lease_id(WORK, 123, 1)
    ack = dict(lease_id=lid, work_id=WORK, executor="SORA",
               timestamp="2026-10-12T10:00:00Z", status="ACKNOWLEDGED")
    assert ack_schema(ack, work_id=WORK, lease=lid, executor="SORA")["status"] == "UNKNOWN"

@pytest.mark.parametrize("bad_work,bad_lease,bad_executor", [
    ("issue:0", None, None),
    ("issue:79", None, None),
    (0, None, None),
    (None, None, None),
    (None, 123, None),
    (None, None, 123),
    (None, None, ""),
])
def test_ack_invalid_identity_types_fail_closed(bad_work, bad_lease, bad_executor):
    lid = lease_id(WORK, 123, 1)
    ack = dict(lease_id=lid, work_id=WORK, executor="SORA",
               run_id=456, timestamp="2026-10-12T10:00:00Z", status="ACKNOWLEDGED")
    result = ack_schema(
        ack,
        work_id=WORK if bad_work is None else bad_work,
        lease=lid if bad_lease is None else bad_lease,
        executor="SORA" if bad_executor is None else bad_executor,
    )
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "INVALID_IDENTITY"
