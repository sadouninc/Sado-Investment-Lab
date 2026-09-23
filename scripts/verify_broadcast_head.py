from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from scripts.update_broadcast_head import MARKER_RE


class BroadcastVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "BROADCAST_SYNC_UNVERIFIED"


@dataclass(frozen=True)
class BroadcastHead:
    comment_id: int
    comments: int


@dataclass(frozen=True)
class BroadcastVerification:
    status: BroadcastVerificationStatus
    head: BroadcastHead | None
    reason: str | None = None


def parse_broadcast_head(issue_body: str) -> BroadcastHead:
    if not isinstance(issue_body, str) or not issue_body:
        raise ValueError("issue body must be a non-empty string")
    matches = list(MARKER_RE.finditer(issue_body))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one broadcast-head marker, found {len(matches)}")
    match = matches[0]
    comment_id = int(match.group(1))
    comments = int(match.group(2))
    if comment_id <= 0 or comments < 0:
        raise ValueError("broadcast-head marker values are invalid")
    return BroadcastHead(comment_id=comment_id, comments=comments)


def verify_broadcast_head(issue_body: str, fetched_comment_ids: Iterable[int]) -> BroadcastVerification:
    try:
        head = parse_broadcast_head(issue_body)
    except (TypeError, ValueError) as exc:
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, None, str(exc))

    try:
        ids = tuple(fetched_comment_ids)
    except TypeError:
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, head, "comment evidence is not iterable")

    if any(isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0 for comment_id in ids):
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, head, "comment evidence contains an invalid id")
    if len(set(ids)) != len(ids):
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, head, "comment evidence contains duplicate ids")
    if ids != tuple(sorted(ids)):
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, head, "comment evidence is not ordered")
    if not ids:
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, head, "comment evidence is empty")
    if head.comment_id not in ids:
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, head, "authoritative head was not fetched")
    if ids[-1] != head.comment_id:
        return BroadcastVerification(BroadcastVerificationStatus.UNVERIFIED, head, "fetched evidence extends beyond authoritative head")

    return BroadcastVerification(BroadcastVerificationStatus.VERIFIED, head)
