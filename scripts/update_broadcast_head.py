from __future__ import annotations

import argparse
import re
from pathlib import Path


MARKER_RE = re.compile(r"<!-- broadcast-head: comment_id=(\d+) comments=(\d+) -->")


class BroadcastHeadMarkerError(ValueError):
    """Raised when the authoritative Broadcast head marker cannot be updated safely."""


def render_marker(*, comment_id: int, comments: int) -> str:
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        raise BroadcastHeadMarkerError("comment_id must be a positive integer")
    if isinstance(comments, bool) or not isinstance(comments, int) or comments < 0:
        raise BroadcastHeadMarkerError("comments must be a non-negative integer")
    return f"<!-- broadcast-head: comment_id={comment_id} comments={comments} -->"


def replace_broadcast_head(body: str, *, comment_id: int, comments: int) -> str:
    if not isinstance(body, str) or not body:
        raise BroadcastHeadMarkerError("issue body must be a non-empty string")

    matches = list(MARKER_RE.finditer(body))
    if len(matches) != 1:
        raise BroadcastHeadMarkerError(
            f"expected exactly one broadcast-head marker, found {len(matches)}"
        )

    replacement = render_marker(comment_id=comment_id, comments=comments)
    match = matches[0]
    return body[: match.start()] + replacement + body[match.end() :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Issue #99 broadcast-head marker safely")
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--comment-id", required=True, type=int)
    parser.add_argument("--comments", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    body = Path(args.body_file).read_text(encoding="utf-8")
    updated = replace_broadcast_head(
        body,
        comment_id=args.comment_id,
        comments=args.comments,
    )
    Path(args.output_file).write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
