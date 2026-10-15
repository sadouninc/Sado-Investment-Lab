"""Conservative read-only preflight for Sora recovery. No dispatch authority.

This check only holds ambiguous candidates; it cannot prove an empty inventory
or authorize a GitHub mutation. The caller must attest complete API snapshots,
fresh Owner/path gates and canonical state before any write.
"""
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping

CONTRACT = (
    re.compile(r"^## Recovery Work Contract[^\n]*$", re.M),
    re.compile(r"^\*\*Priority:\*\* P[01]\b", re.M),
    re.compile(r"^\*\*Flow Authority:\*\* .*ナギ", re.M),
    re.compile(r"^\*\*Recovery Engineer:\*\* .*ソラ", re.M),
)


def _block(reason: str, **details: object) -> dict:
    return {"status": "BLOCKED", "reason": reason, **details}


def _related_event(body: str, issue_number: int) -> bool:
    """Parse embedded JSON, including multiline and Unicode-escaped identities."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", body):
        try:
            obj, _ = decoder.raw_decode(body, match.start())
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("work_ref") == f"issue:{issue_number}":
            return True
        if obj.get("work_id") == f"issue:{issue_number}":
            return True
        if obj.get("owner_slice") == f"issue-{issue_number}":
            return True
        if obj.get("target_issue") in (issue_number, str(issue_number)):
            return True
        if obj.get("issue_number") in (issue_number, str(issue_number)) and any(
            k in obj for k in ("status", "action", "lease_id", "canonical_lease_id")
        ):
            return True
    return False


def check_candidate(issue: Mapping, comments: list, prs: list) -> dict:
    """Preliminary read-only eligibility; ALLOW is never dispatch authorization."""
    if not isinstance(issue, Mapping):
        return _block("INVALID_ISSUE")
    number = issue.get("number")
    if type(number) is not int or number <= 0 or number == 79:
        return _block("INVALID_OR_PROTECTED_ISSUE")
    body = issue.get("body")
    if issue.get("state") != "open" or issue.get("pull_request") is not None or not isinstance(body, str):
        return _block("ISSUE_NOT_ELIGIBLE")
    if not all(p.search(body) for p in CONTRACT):
        return _block("RECOVERY_CONTRACT_MISSING")
    if not isinstance(comments, list) or not isinstance(prs, list):
        return _block("EVIDENCE_INCOMPLETE")
    ids: set[int] = set()
    for comment in comments:
        if not isinstance(comment, Mapping) or type(comment.get("id")) is not int or comment["id"] <= 0:
            return _block("INVALID_COMMENT")
        if comment["id"] in ids:
            return _block("DUPLICATE_COMMENT")
        ids.add(comment["id"])
        text = comment.get("body")
        if not isinstance(text, str) or len(text) > 200_000:
            return _block("INVALID_OR_OVERSIZE_COMMENT")
        if ("AUTO_ROUTER_DISPATCH" in text and
                re.search(r"target_issue\s*=\s*" + str(number) + r"\b", text)):
            return _block("PRIOR_DISPATCH_REQUIRES_RECONCILIATION")
        if _related_event(text, number):
            return _block("UNRECONCILED_WORK_EVENT")
    issue_ref = re.compile(r"(?<!\d)#" + str(number) + r"(?!\d)")
    branch_ref = re.compile(r"(?:^|[/_-])(?:issue[-_])?" + str(number) + r"(?:$|[/_-])")
    seen_pr_numbers: set[int] = set()
    for pr in prs:
        if not isinstance(pr, Mapping) or type(pr.get("number")) is not int or pr["number"] <= 0:
            return _block("INVALID_PR_INVENTORY")
        if pr["number"] in seen_pr_numbers:
            return _block("DUPLICATE_PR_INVENTORY")
        seen_pr_numbers.add(pr["number"])
        if pr.get("state") not in ("open", "closed"):
            return _block("PR_STATE_UNKNOWN")
        if not isinstance(pr.get("title"), str) or (
            pr.get("body") is not None and not isinstance(pr.get("body"), str)
        ):
            return _block("INVALID_PR_METADATA")
        head = pr.get("head")
        if head is not None and (
            not isinstance(head, Mapping) or not isinstance(head.get("ref"), str)
        ):
            return _block("INVALID_PR_HEAD")
        ref = head["ref"] if head is not None else ""
        if issue_ref.search(pr["title"]) or issue_ref.search(pr.get("body") or "") or branch_ref.search(ref):
            return _block("RELATED_PR_EXISTS", pr_number=pr["number"])
    return {"status": "ALLOW_PRELIMINARY", "reason": "FRESH_ATTESTED_PREFLIGHT_REQUIRED",
            "issue_number": number, "dispatch_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--prs-json", required=True)
    args = parser.parse_args()
    try:
        with open(args.issue_json, encoding="utf-8") as f:
            issue = json.load(f)
        with open(args.comments_json, encoding="utf-8") as f:
            comments = json.load(f)
        with open(args.prs_json, encoding="utf-8") as f:
            prs = json.load(f)
        result = check_candidate(issue, comments, prs)
    except (OSError, ValueError, TypeError):
        result = _block("EVIDENCE_READ_FAILURE")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ALLOW_PRELIMINARY" else 78


if __name__ == "__main__":
    raise SystemExit(main())
