"""Read-only, fail-closed projection of GitHub Actions owner/lease evidence.

Inputs are independently retrieved GitHub snapshots; this module does not write,
issue leases, dispatch work, or claim to authenticate a comment by its author.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

DOMAINS = ("issues", "pull_requests", "branches", "actions_runs", "owner_lease_ledger")
ACTIVE = frozenset(("ASSIGNED", "ACKNOWLEDGED", "FALLBACK_ASSIGNED"))


def diagnose_owner_ledger_source(*, repository: str, workflow_run_id: int | None,
                                 artifact_inventory: Mapping[str, Any] | None) -> dict[str, Any]:
    """Observe a candidate Actions artifact inventory; never certify its authority.

    The caller must retrieve the inventory via read-only GitHub API. An artifact
    name or self-declared run ID cannot establish a canonical Owner/Lease issuer.
    """
    result = {"status": "UNKNOWN", "reason": "SOURCE_UNVERIFIED",
              "dispatch_allowed": False, "candidate_artifacts": [],
              "first_missing_source": "canonical_owner_lease_ledger_issuer"}
    if not isinstance(repository, str) or "/" not in repository:
        return {**result, "reason": "INVALID_REPOSITORY"}
    if type(workflow_run_id) is not int or workflow_run_id <= 0:
        return {**result, "reason": "ACTIONS_RUN_UNVERIFIED"}
    if not isinstance(artifact_inventory, Mapping):
        return {**result, "reason": "ARTIFACT_INVENTORY_UNAVAILABLE"}
    artifacts = artifact_inventory.get("artifacts")
    total = artifact_inventory.get("total_count")
    if not isinstance(artifacts, list) or type(total) is not int or total != len(artifacts):
        return {**result, "reason": "INCOMPLETE_ARTIFACT_INVENTORY"}
    candidates = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            return {**result, "reason": "MALFORMED_ARTIFACT_INVENTORY"}
        name = artifact.get("name")
        if isinstance(name, str) and any(token in name.lower() for token in ("owner", "lease", "ledger")):
            candidates.append({"id": artifact.get("id"), "name": name,
                               "expired": artifact.get("expired")})
    return {**result, "candidate_artifacts": candidates}


def _overlap(a: str, b: str) -> bool:
    """Conservatively reject exact and directory/file nested path ownership."""
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")



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

    runs: dict[int, Mapping[str, Any]] = {}
    for run in domains["actions_runs"]["items"]:
        if not isinstance(run, Mapping) or type(run.get("id")) is not int:
            return _unknown("MALFORMED_ACTIONS_RUN")
        run_id = run["id"]
        if run_id in runs and dict(runs[run_id]) != dict(run):
            return _unknown("CONFLICTING_ACTIONS_RUN_RECORDS")
        runs[run_id] = run
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    occupied: dict[str, str] = {}
    lease_owners: dict[str, str] = {}
    terminated: set[str] = set()
    for claim in domains["owner_lease_ledger"]["items"]:
        if not isinstance(claim, Mapping):
            return _unknown("MALFORMED_CLAIM")
        # All-actor scope: a foreign work item can still occupy these paths.
        # An unverified foreign claim cannot establish conflict-free ownership.
        foreign_work = claim.get("work_id") != work_id
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
        if lease in lease_owners and lease_owners[lease] != owner:
            return _unknown("CONFLICTING_LEASE_OWNER")
        lease_owners[lease] = owner
        if foreign_work:
            # Never silently ignore an active pre-PR claim from another work.
            # Its terminal history also needs independent reconciliation.
            return _unknown("ALL_ACTOR_SCOPE_RECONCILIATION_REQUIRED")
        if claim["status"] in ("STOP", "RELEASE", "REVOKED"):
            # Never accept a terminal event as proof of release without an
            # independently attested matching active lease and ordering.
            if lease not in {c["lease_id"] for c in claims} or lease in terminated:
                return _unknown("UNMATCHED_OR_REPEATED_TERMINAL_EVENT")
            if any(c["lease_id"] == lease and
                   (c["owner"] != owner or c["exact_paths"] != paths)
                   for c in claims):
                return _unknown("TERMINAL_SCOPE_MISMATCH")
            terminated.add(lease)
            for path in paths:
                if occupied.get(path) == lease:
                    del occupied[path]
            claims = [c for c in claims if c["lease_id"] != lease]
            continue
        if lease in terminated:
            return _unknown("ACTIVE_AFTER_TERMINAL_EVENT")
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
                if any(_overlap(path, existing) and active_lease != lease
                       for existing, active_lease in occupied.items()):
                    return _unknown("CONFLICTING_OWNER_PATHS")
                occupied[path] = lease
        identity = (lease, claim["status"])
        if identity in seen:
            return _unknown("DUPLICATE_CLAIM")
        seen.add(identity)
        claims.append(dict(claim))
    # Snapshot flags and run_artifact_verified are caller assertions, NOT
    # independently authenticated GitHub evidence. Never expose this output
    # as a production-ready attested inventory without a trusted fetch layer.
    return {"status": "COMPLETE" if claims else "COMPLETE_EMPTY",
            "reason": "PROJECTION_ONLY_EXTERNAL_ATTESTATION_REQUIRED", "claims": claims,
            "source_refs": refs, "dispatch_allowed": False}


def collect_authenticated_owner_claims(
    *, work_id: str, fetch_page, verify_run_artifact, now: datetime | None = None,
    max_pages: int = 100,
) -> dict[str, Any]:
    """Read GitHub evidence through injected *read-only* API functions.

    fetch_page(domain, page, per_page=100) returns a mapping with items,
    next_page (integer or None), and immutable source_ref. Every page is
    traversed; failures and unverified artifacts fail closed. A boolean
    embedded in an issue comment is never treated as attestation.
    verify_run_artifact(claim, run) must independently verify the run-owned
    artifact and return True; this function does not trust claim flags.
    """
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79",
                "claims": [], "source_refs": None, "dispatch_allowed": False}
    if not isinstance(work_id, str) or not work_id.startswith("issue:"):
        return _unknown("INVALID_WORK_ID")
    if not callable(fetch_page) or not callable(verify_run_artifact):
        return _unknown("SOURCE_READER_UNAVAILABLE")
    domains: dict[str, dict[str, Any]] = {}
    for name in DOMAINS:
        items: list[Any] = []
        refs: list[str] = []
        page = 1
        visited: set[int] = set()
        while page is not None:
            if page in visited or len(visited) >= max_pages:
                return _unknown("INCOMPLETE_PAGINATION")
            visited.add(page)
            try:
                response = fetch_page(name, page, per_page=100)
            except Exception:
                return _unknown("SOURCE_FETCH_FAILED")
            if not isinstance(response, Mapping):
                return _unknown("SOURCE_UNVERIFIED")
            chunk, ref = response.get("items"), response.get("source_ref")
            next_page = response.get("next_page")
            if (not isinstance(chunk, list) or not isinstance(ref, str)
                    or not ref or response.get("fresh") is not True
                    or (next_page is not None and
                        (type(next_page) is not int or next_page <= page))):
                return _unknown("SOURCE_UNVERIFIED")
            items.extend(chunk)
            refs.append(ref)
            page = next_page
        domains[name] = {"items": items, "complete": True, "fresh": True,
                         "source_ref": tuple(refs)}
    runs: dict[int, Mapping[str, Any]] = {}
    for run in domains["actions_runs"]["items"]:
        if not isinstance(run, Mapping) or type(run.get("id")) is not int:
            return _unknown("MALFORMED_ACTIONS_RUN")
        if run["id"] in runs and dict(runs[run["id"]]) != dict(run):
            return _unknown("CONFLICTING_ACTIONS_RUN_RECORDS")
        runs[run["id"]] = run
    verified_claims: list[dict[str, Any]] = []
    for claim in domains["owner_lease_ledger"]["items"]:
        if not isinstance(claim, Mapping):
            return _unknown("MALFORMED_CLAIM")
        # Verify all actors, including pre-PR and other-work claims, before
        # attempting a conflict-free inventory for this work.
        run_id = claim.get("writer_run_id")
        run = runs.get(run_id) if type(run_id) is int else None
        if run is None:
            return _unknown("ISSUER_RUN_ATTESTATION_MISSING")
        try:
            verified = verify_run_artifact(claim, run) is True
        except Exception:
            return _unknown("ISSUER_RUN_ATTESTATION_MISSING")
        if not verified:
            return _unknown("ISSUER_RUN_ATTESTATION_MISSING")
        # Never elevate caller-provided assertion flags without checking.
        verified_claim = dict(claim)
        verified_claim["run_artifact_verified"] = True
        verified_claim["artifact_run_id"] = run_id
        verified_claims.append(verified_claim)
    domains["owner_lease_ledger"]["items"] = verified_claims
    result = project_owner_claim_source(work_id=work_id, domains=domains, now=now)
    # Independent source/claim verification still does not establish all-actor
    # cross-domain exclusivity. Do not export a production COMPLETE inventory.
    if result["status"] in ("COMPLETE", "COMPLETE_EMPTY"):
        return _unknown("CROSS_DOMAIN_CLAIM_RECONCILIATION_REQUIRED")
    return result
