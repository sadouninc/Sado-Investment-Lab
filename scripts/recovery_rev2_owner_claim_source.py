"""Read-only, fail-closed projection of GitHub Actions owner/lease evidence.

Inputs are independently retrieved GitHub snapshots; this module does not write,
issue leases, dispatch work, or claim to authenticate a comment by its author.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

DOMAINS = ("issues", "pull_requests", "branches", "actions_runs", "owner_lease_ledger")
ACTIVE = frozenset(("ASSIGNED", "ACKNOWLEDGED", "FALLBACK_ASSIGNED"))


def _unknown(reason: str) -> dict[str, Any]:
    return {"status": "UNKNOWN", "reason": reason, "claims": [],
            "source_refs": None, "dispatch_allowed": False}


def project_owner_claim_source(
    *, work_id: str, domains: Mapping[str, Mapping[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Require complete, fresh five-domain snapshots and run-owned lease evidence.

    Each domain snapshot must carry items, complete, fresh, and source_ref.
    Claim records in owner_lease_ledger must contain an independently verified
    run-owned artifact binding (not merely a self-declared run ID).
    """
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79",
                "claims": [], "source_refs": None, "dispatch_allowed": False}
    if not isinstance(work_id, str) or not work_id.startswith("issue:"):
        return _unknown("INVALID_WORK_ID")
    if not isinstance(domains, Mapping):
        return _unknown("SOURCE_UNAVAILABLE")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return _unknown("CLOCK_UNVERIFIED")
    refs: dict[str, Any] = {}
    for name in DOMAINS:
        domain = domains.get(name)
        if not isinstance(domain, Mapping):
            return _unknown("SOURCE_COVERAGE_MISSING")
        if domain.get("complete") is not True:
            return _unknown("INCOMPLETE_PAGINATION")
        if domain.get("fresh") is not True:
            return _unknown("SOURCE_STALE")
        if not domain.get("source_ref") or not isinstance(domain.get("items"), list):
            return _unknown("SOURCE_UNVERIFIED")
        refs[name] = domain["source_ref"]

    runs = {r.get("id"): r for r in domains["actions_runs"]["items"]
            if isinstance(r, Mapping) and type(r.get("id")) is int}
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    occupied: dict[str, str] = {}
    for claim in domains["owner_lease_ledger"]["items"]:
        if not isinstance(claim, Mapping):
            return _unknown("MALFORMED_CLAIM")
        if claim.get("work_id") != work_id:
            continue
        if claim.get("status") not in ACTIVE:
            if claim.get("status") in ("STOP", "RELEASE", "REVOKED"):
                # A terminal event requires authenticated provenance as well.
                pass
            else:
                return _unknown("UNKNOWN_LEASE_STATUS")
        run_id = claim.get("writer_run_id")
        run = runs.get(run_id) if type(run_id) is int else None
        if (not run or run.get("conclusion") != "success"
                or claim.get("run_artifact_verified") is not True
                or claim.get("artifact_run_id") != run_id
                or claim.get("issuer") != "github-actions"):
            return _unknown("ISSUER_RUN_ATTESTATION_MISSING")
        owner, lease = claim.get("owner"), claim.get("lease_id")
        paths = claim.get("exact_paths")
        if (not isinstance(owner, str) or not owner or
                not isinstance(lease, str) or not lease or
                not isinstance(paths, list) or not paths or
                any(not isinstance(p, str) or not p or "*" in p for p in paths)):
            return _unknown("INVALID_CLAIM_SCOPE")
        if claim["status"] in ACTIVE:
            if claim.get("ack_verified") is not True:
                return _unknown("ACK_UNVERIFIED")
            expiry = claim.get("expires_at")
            try:
                deadline = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                return _unknown("LEASE_EXPIRY_UNVERIFIED")
            if deadline.tzinfo is None or deadline <= now:
                return _unknown("LEASE_EXPIRED_OR_UNVERIFIED")
            for path in paths:
                if path in occupied and occupied[path] != lease:
                    return _unknown("CONFLICTING_OWNER_PATHS")
                occupied[path] = lease
        identity = (lease, claim["status"])
        if identity in seen:
            return _unknown("DUPLICATE_CLAIM")
        seen.add(identity)
        claims.append(dict(claim))
    return {"status": "COMPLETE" if claims else "COMPLETE_EMPTY",
            "reason": "ATTESTED_SOURCE_SNAPSHOT", "claims": claims,
            "source_refs": refs, "dispatch_allowed": False}
