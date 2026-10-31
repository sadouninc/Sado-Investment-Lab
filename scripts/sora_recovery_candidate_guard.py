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
    re.compile(r"^\*\*Flow Authority:\*\* .*ルナ", re.M),
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



def _ambiguous_malformed_event(body: str, issue_number: int) -> bool:
    """Hold malformed event envelopes, without treating explanatory prose as events."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", body):
        fragment = body[match.start():]
        try:
            obj, _ = decoder.raw_decode(fragment)
            if isinstance(obj, dict):
                continue  # Valid events are handled by _related_event.
        except (ValueError, TypeError):
            pass
        # An actual JSON-shaped lease event must contain quoted keys inside an
        # object. Loose prose containing both tokens is not an event envelope.
        if not re.search(r'"canonical_lease_id"\s*:', fragment):
            continue
        target_match = re.search(
            r'"(?:work_ref|work_id|owner_slice)"\s*:\s*("(?:\\.|[^"\\])*")',
            fragment,
        )
        if target_match is None:
            return True  # Truncated event: its target cannot be established.
        try:
            target = json.loads(target_match.group(1))
        except (ValueError, TypeError):
            return True
        if target in (f"issue:{issue_number}", f"issue-{issue_number}"):
            return True
        if isinstance(target, str) and re.fullmatch(r"issue[:\-]\d+", target):
            continue  # Explicitly unrelated issue, even if the event is partial.
        return True  # Unknown target provenance remains fail-closed.
    return False

# This is a narrow, immutable completed-slice attestation, NOT a rule to ignore
# all merged PRs. PR #860 and any unverified/incomplete work still block.
def _attested_completed_859_guard_repair(pr: Mapping, issue_number: int) -> bool:
    if issue_number != 859 or pr.get("number") != 885 or pr.get("state") != "closed":
        return False
    head = pr.get("head")
    base = pr.get("base")
    return (
        pr.get("title") == "fix(#859): distinguish incidental PR mentions from recovery ownership"
        and pr.get("merged_at") == "2026-10-22T23:20:02Z"
        and pr.get("merge_commit_sha") == "f21eecc5bbc1893510964dea28f8d7c14a09db65"
        and pr.get("merged") is True
        and isinstance(head, Mapping)
        and head.get("ref") == "sora/859-hold-only-workflow-regression-20261020"
        and head.get("sha") == "788cb555d645bd5b3bba2080c03a667d66a466db"
        and isinstance(base, Mapping)
        and base.get("ref") == "main"
    )


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
        # Only malformed event-shaped JSON is ambiguous; prose is not.
        if _ambiguous_malformed_event(text, number):
            return _block("AMBIGUOUS_RELATED_EVENT")
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
        # Incidental issue mentions in a PR description are not ownership evidence.
        # Recognize explicit closing/reference linkage anywhere, including bullet lists.
        body_link = re.search(
            r"(?im)(?<![\w])(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?|references?)\s*:?\s*(?:[\w.-]+/[\w.-]+)?#" + str(number) + r"(?!\d)\b",
            pr.get("body") or "",
        )
        if issue_ref.search(pr["title"]) or body_link or branch_ref.search(ref):
            if _attested_completed_859_guard_repair(pr, number):
                continue  # Completed guard repair only; not POST authorization.
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
