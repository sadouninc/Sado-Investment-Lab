"""Read-only diagnostic for one queue candidate. Never authorizes dispatch.

Issue #943: open PRs do not attest to exclusive pre-PR ownership.
A fully fetched PR list is not a complete Owner/Lease inventory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def _paths_overlap(a: str, b: str) -> bool:
    if not a or not b:
        return True  # Ambiguous path is not safe.
    # Both glob scopes and bare directory scopes may denote descendants.
    # A prefix ending at a path boundary is conservatively treated as a
    # conflict. "scripts/foo.py" must not match "scripts/foo.py.bak".
    def prefix(s: str) -> str:
        return s[:-3] if s.endswith("/**") else s.rstrip("/")
    left, right = prefix(a), prefix(b)
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def inspect_one_candidate(
    issues: Any,
    open_pr_inventory: Any,
) -> dict[str, Any]:
    """Classify evidence, NOT eligibility for dispatch. The output is always HOLD.

    issues: a normalized bounded JSON list with number, allowed_paths, owner_slice.
    open_pr_inventory: {'complete': bool, 'prs': [{'number', 'paths': [...]}]}
    'complete' only describes the *PR path list*. It is NOT an Owner/Lease proof.
    """
    result: dict[str, Any] = {
        "status": "HOLD",
        "reason": "OWNER_ISSUER_UNVERIFIED",
        "dispatch_allowed": False,
        "selected_issue": None,
        "candidate_count": 0,
        "conflicting_prs": [],
        "missing_evidence": ["canonical_owner_lease_issuer", "authenticated_owner_lease_inventory"],
    }
    if not isinstance(issues, list):
        return {**result, "reason": "ISSUE_INVENTORY_INCOMPLETE"}
    eligible = [i for i in issues if isinstance(i, Mapping) and type(i.get("number")) is int
                and i["number"] > 0 and i["number"] != 79]
    result["candidate_count"] = len(eligible)
    if not eligible:
        return {**result, "reason": "NO_READY_CANDIDATE"}
    chosen = eligible[0]
    result["selected_issue"] = chosen["number"]
    paths = chosen.get("allowed_paths")
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not p for p in paths):
        return {**result, "reason": "ISSUE_PATH_SCOPE_UNVERIFIED"}
    if not chosen.get("owner_slice") or not isinstance(chosen["owner_slice"], str):
        return {**result, "reason": "OWNER_SLICE_UNVERIFIED"}
    if (not isinstance(open_pr_inventory, Mapping)
            or open_pr_inventory.get("complete") is not True
            or not isinstance(open_pr_inventory.get("prs"), list)):
        return {**result, "reason": "PR_PATH_INVENTORY_INCOMPLETE"}
    conflicts: list[int] = []
    seen: set[int] = set()
    for pr in open_pr_inventory["prs"]:
        if (not isinstance(pr, Mapping) or type(pr.get("number")) is not int
                or pr["number"] <= 0 or pr["number"] in seen
                or not isinstance(pr.get("paths"), list)
                or not pr["paths"]
                or any(not isinstance(p, str) or not p for p in pr["paths"])):
            return {**result, "reason": "PR_PATH_INVENTORY_INCOMPLETE"}
        seen.add(pr["number"])
        if any(_paths_overlap(path, other) for path in paths for other in pr["paths"]):
            conflicts.append(pr["number"])
    if conflicts:
        return {**result, "reason": "PR_PATH_CONFLICT", "conflicting_prs": conflicts}
    # A complete open-PR path inventory does NOT prove pre-PR owner/lease claims.
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only owner-inventory pilot; never dispatches.")
    parser.add_argument("--issues", required=True)
    parser.add_argument("--open-prs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        issues = json.loads(Path(args.issues).read_text(encoding="utf-8"))
        prs = json.loads(Path(args.open_prs).read_text(encoding="utf-8"))
        report = inspect_one_candidate(issues, prs)
    except (OSError, ValueError):
        report = {"status": "HOLD", "reason": "INPUT_UNAVAILABLE", "dispatch_allowed": False,
                  "selected_issue": None, "candidate_count": 0, "conflicting_prs": [],
                  "missing_evidence": ["valid_readonly_inputs"]}
    try:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n",
                                     encoding="utf-8")
    except OSError:
        # Do not suppress the failed artifact write as a successful HOLD run.
        error = {**report, "status": "HOLD", "reason": "OUTPUT_UNAVAILABLE",
                 "dispatch_allowed": False}
        print(json.dumps(error, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
