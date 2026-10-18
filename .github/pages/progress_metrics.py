"""Pure evidence-based progress calculations; no GitHub API or side effects."""

VALID_STATES = frozenset({"PASS", "FAIL", "BLOCKED", "UNKNOWN"})
DIMENSIONS = ("implementation", "verification", "production")


def summarize(criteria, dimension):
    """Return PASS/denominator only for a finalized, nonempty criterion set."""
    if dimension not in DIMENSIONS:
        raise ValueError("invalid dimension")
    selected = [c for c in criteria if c["dimension"] == dimension]
    if not selected or any(not c.get("finalized", False) for c in selected):
        return {"passed": None, "total": None, "percent": None, "status": "UNKNOWN"}
    if len({c["criterion_id"] for c in selected}) != len(selected):
        raise ValueError("duplicate criterion_id")
    for criterion in selected:
        if criterion["state"] not in VALID_STATES:
            raise ValueError("invalid state")
    passed = sum(c["state"] == "PASS" and bool(c.get("evidence_url")) for c in selected)
    return {
        "passed": passed,
        "total": len(selected),
        "percent": round(100 * passed / len(selected), 1),
        "status": "VERIFIED" if passed == len(selected) else "INCOMPLETE",
    }


def compare_snapshots(previous, current):
    """Compare only equal-scope snapshots; scope changes stay separate."""
    old = {c["criterion_id"]: c for c in previous["criteria"]}
    new = {c["criterion_id"]: c for c in current["criteria"]}
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    if previous["scope_version"] != current["scope_version"] or added or removed:
        return {
            "status": "SCOPE_CHANGED",
            "scope_delta": {"added": added, "removed": removed},
            "newly_passed": None,
            "regressed": None,
            "new_blockers": None,
            "resolved_blockers": None,
            "remaining_blockers": None,
        }
    def verified(c):
        return c["state"] == "PASS" and bool(c.get("evidence_url"))
    def blocked(c):
        return c["state"] == "BLOCKED"
    return {
        "status": "COMPARABLE",
        "scope_delta": {"added": [], "removed": []},
        "newly_passed": sorted(k for k in new if not verified(old[k]) and verified(new[k])),
        "regressed": sorted(k for k in new if verified(old[k]) and not verified(new[k])),
        "new_blockers": sorted(k for k in new if not blocked(old[k]) and blocked(new[k])),
        "resolved_blockers": sorted(k for k in new if blocked(old[k]) and not blocked(new[k])),
        "remaining_blockers": sorted(k for k in new if blocked(new[k])),
    }


STEPS = ("READY", "LEASE", "ACK", "COMMIT", "PR", "LATEST_HEAD_CI",
         "REVIEW_GATE", "MERGE_SHA", "NEXT_AUTO")


def closed_loop(steps):
    """Only one consistently linked work/lease can count as a complete set."""
    if len(steps) != len(STEPS) or [s["step"] for s in steps] != list(STEPS):
        return {"passed": 0, "total": 9, "complete": 0}
    work_refs = {s.get("work_ref") for s in steps}
    lease_ids = {s.get("lease_id") for s in steps}
    linked = len(work_refs) == 1 and None not in work_refs and len(lease_ids) == 1 and None not in lease_ids
    passed = sum(s.get("state") == "PASS" and bool(s.get("evidence_url")) for s in steps) if linked else 0
    return {"passed": passed, "total": 9, "complete": int(linked and passed == 9)}
