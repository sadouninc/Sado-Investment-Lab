"""Read-only Rev.2 bridge from attested comments to state projection.

Attestation MUST be established independently by caller against GitHub API and
Actions run metadata. This module cannot authorize dispatch or merge.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from scripts.recovery_rev2_evidence_adapter import canonical_event
from scripts.recovery_rev2_state_reader import project_state

def project_attested_comments(*, work_id: str, comments: Sequence[Mapping],
                              trusted_comment_ids: set[int],
                              provenance_verified: bool) -> dict:
    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79", "dispatch_allowed": False}
    if provenance_verified is not True or not isinstance(comments, (list, tuple)):
        return {"status": "UNKNOWN", "reason": "PROVENANCE_UNVERIFIED", "dispatch_allowed": False}
    if not isinstance(trusted_comment_ids, set) or len(comments) != len(trusted_comment_ids):
        return {"status": "UNKNOWN", "reason": "ATTESTATION_SET_MISMATCH", "dispatch_allowed": False}
    # The caller must provide a complete, unique, ordered set of real
    # GitHub comment IDs. A trusted-ID set alone does not prove that the
    # supplied comments form a valid ordered event history.
    ids = [comment.get("id") if isinstance(comment, Mapping) else None
           for comment in comments]
    if (any(type(cid) is not int or cid <= 0 for cid in ids)
            or ids != sorted(ids) or len(ids) != len(set(ids))
            or set(ids) != trusted_comment_ids):
        return {"status": "UNKNOWN", "reason": "INVALID_ATTESTED_COMMENT_INVENTORY",
                "dispatch_allowed": False}
    # Do not accept arbitrary comment JSON merely because the caller supplied
    # a matching ID set. Canonical Rev.2 events must be authored by the
    # expected GitHub Actions identity; independent run provenance is still
    # mandatory at the caller boundary.
    for comment in comments:
        author = comment.get("user")
        if not isinstance(author, Mapping) or author.get("login") != "github-actions[bot]":
            return {"status": "UNKNOWN", "reason": "UNTRUSTED_EVENT_AUTHOR",
                    "dispatch_allowed": False}
        # A GitHub bot identity is necessary, never sufficient. The caller's
        # provenance_verified flag must mean that each event was linked to a
        # specific authenticated run, not just that its author looks correct.
        if comment.get("issue_url") is not None:
            expected_suffix = "/issues/" + work_id.split(":", 1)[1]
            issue_url = comment.get("issue_url")
            if not isinstance(issue_url, str) or not issue_url.endswith(expected_suffix):
                return {"status": "UNKNOWN", "reason": "COMMENT_ISSUE_MISMATCH",
                        "dispatch_allowed": False}
    events = []
    for comment in comments:
        event = canonical_event(comment, work_id=work_id,
                                trusted_comment_ids=trusted_comment_ids)
        if event.get("status") in {"UNKNOWN", "BLOCKED"}:
            return {"status": "UNKNOWN", "reason": event.get("reason", "INVALID_EVENT"),
                    "dispatch_allowed": False}
        events.append(event)
    return project_state(work_id=work_id, events=events, evidence_verified=True)


def project_attested_owner_inventory(*, work_id: str, claims: Sequence[Mapping] | None,
                                    source_refs: Mapping | None,
                                    coverage_complete: bool = False,
                                    provenance_verified: bool = False,
                                    freshness_verified: bool = False) -> dict:
    """Project independently attested ownership claims; never grant authority.

    This is a normalized read boundary, NOT a new canonical Owner/Lease ledger.
    The caller must independently verify GitHub API + ledger identity, run/lease
    binding, expiry, ACK, STOP/revocation and consistency before setting the
    provenance/freshness flags. Source strings alone prove nothing. Each of the
    five source domains must be covered, including work without a PR. Until a
    real ledger reader exists, callers must pass unknown and remain HOLD.
    """
    import re

    def hold(reason):
        # Unknown is deliberately not represented as an empty owner collection.
        return {"status": "UNKNOWN", "reason": reason,
                "active_claims": None, "dispatch_allowed": False}

    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79",
                "active_claims": None, "dispatch_allowed": False}
    valid_work = lambda value: isinstance(value, str) and re.fullmatch(r"issue:[1-9][0-9]*", value)
    if not valid_work(work_id):
        return hold("INVALID_WORK_ID")
    if claims is None or source_refs is None:
        return hold("OWNER_INVENTORY_SOURCE_UNAVAILABLE")
    if provenance_verified is not True:
        return hold("OWNER_INVENTORY_PROVENANCE_UNVERIFIED")
    if coverage_complete is not True:
        return hold("OWNER_INVENTORY_INCOMPLETE")
    if freshness_verified is not True:
        return hold("OWNER_INVENTORY_FRESHNESS_UNVERIFIED")
    domains = {"issues", "pull_requests", "branches", "actions_runs", "owner_lease_ledger"}
    if (not isinstance(source_refs, Mapping) or set(source_refs) != domains
            or any(not isinstance(ref, str) or not ref.strip()
                   for ref in source_refs.values())):
        return hold("OWNER_INVENTORY_SOURCE_COVERAGE_MISSING")
    if not isinstance(claims, (list, tuple)):
        return hold("INVALID_OWNER_INVENTORY")
    # These are existing TEAM_STATE work states, not PR-derived owner guesses.
    active = {"EXECUTION_EVIDENCE", "IMPLEMENTING", "REVISION_REQUIRED", "CONFLICT_RESOLUTION"}
    waiting = {"DISPATCHED", "ACKED", "CI_WAIT", "REVIEW_WAIT", "RESEARCH_GATE_WAIT",
               "DESIGN_GATE_WAIT", "OWNER_WAIT", "EXTERNAL_WAIT", "MERGE_READY"}
    projected = []
    seen = set()
    for claim in claims:
        if not isinstance(claim, Mapping):
            return hold("INVALID_OWNER_CLAIM")
        work, owner, state, paths = (claim.get(key) for key in
                                     ("work_id", "owner", "state", "paths"))
        if (not valid_work(work) or not isinstance(owner, str) or not owner.strip()
                or not isinstance(state, str) or state not in active | waiting
                or not isinstance(paths, (list, tuple)) or not paths
                or any(not isinstance(path, str) or not path.strip()
                       or path != path.strip() or path.startswith(("/", "\\"))
                       or "\\" in path or ":" in path
                       or any(part in {"", ".", ".."} for part in path.split("/"))
                       for path in paths)):
            return hold("INVALID_OWNER_CLAIM")
        # Duplicate/conflicting work identities must not be silently collapsed.
        if work == "issue:79":
            return hold("PROTECTED_ISSUE_79")
        if work in seen:
            return hold("CONFLICTING_OWNER_CLAIMS")
        seen.add(work)
        for previous in projected:
            for left in previous["paths"]:
                for right in paths:
                    # Preserve exact, directory and trailing-glob claims. Other
                    # glob syntax is not interpreted as proof of disjointness.
                    a, b = left.removesuffix("/**").rstrip("/"), right.removesuffix("/**").rstrip("/")
                    if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                        return hold("CONFLICTING_OWNER_PATHS")
        if any("*" in path.removesuffix("/**") or "?" in path or "[" in path for path in paths):
            return hold("AMBIGUOUS_OWNER_PATHS")
        # Waiting work does not consume active WIP, but retains owner/path claims.
        projected.append({"work_id": work, "owner": owner, "state": state,
                          "paths": sorted(set(paths)), "active_wip": state in active})
    projected.sort(key=lambda item: (item["work_id"], item["owner"]))
    return {"status": "COMPLETE" if projected else "COMPLETE_EMPTY",
            "reason": "ATTESTED_OWNER_INVENTORY", "active_claims": projected,
            "source_refs": dict(source_refs), "dispatch_allowed": False}


def project_verified_copilot_linkage_inventory(*, work_id: str,
                                               observed_comment_ids: Sequence,
                                               verified_linkages: Sequence[Mapping],
                                               source_complete: bool) -> dict:
    """Project independently verified B1 linkage evidence without authorizing POST.

    Empty history is UNKNOWN, and a partial artifact inventory is never READY.
    This is not the canonical five-domain Owner/Lease inventory.
    """
    def hold(reason: str) -> dict:
        return {"status": "UNKNOWN", "reason": reason, "dispatch_allowed": False,
                "observed_count": len(observed_comment_ids) if isinstance(observed_comment_ids, (list, tuple)) else None,
                "authenticated_count": 0}

    if work_id == "issue:79":
        return {"status": "BLOCKED", "reason": "PROTECTED_ISSUE_79",
                "dispatch_allowed": False, "authenticated_count": 0}
    if (not isinstance(observed_comment_ids, (list, tuple))
            or not isinstance(verified_linkages, (list, tuple))):
        return hold("INVALID_B1_EVIDENCE")
    if source_complete is not True:
        return hold("COPILOT_B1_SOURCE_INCOMPLETE")
    if not observed_comment_ids:
        return hold("COPILOT_B1_NO_OBSERVED_ASSIGNMENT")
    ids = [linkage.get("comment_id") if isinstance(linkage, Mapping) else None
           for linkage in verified_linkages]
    if (len(ids) != len(observed_comment_ids)
            or any(type(cid) is not int or cid <= 0 for cid in ids)
            or len(set(ids)) != len(ids)
            or len(set(observed_comment_ids)) != len(observed_comment_ids)
            or set(ids) != set(observed_comment_ids)):
        return hold("COPILOT_B1_ATTESTATION_SET_MISMATCH")
    if any(linkage.get("status") != "ATTESTED_LINKAGE"
           or linkage.get("work_id") != work_id
           or linkage.get("dispatch_allowed") is not False
           for linkage in verified_linkages):
        return hold("COPILOT_B1_IDENTITY_MISMATCH")
    # All observed assignments have independent run/artifact/comment linkage,
    # but neither canonical owner inventory nor ACK/STOP/expiry history follows.
    return {"status": "LINKAGE_ATTESTED", "reason": "COPILOT_B1_LINKAGES_CORRELATED",
            "observed_count": len(observed_comment_ids),
            "authenticated_count": len(verified_linkages),
            "dispatch_allowed": False}
