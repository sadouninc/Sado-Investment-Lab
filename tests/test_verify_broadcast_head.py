import pytest

from scripts.verify_broadcast_head import (
    BroadcastVerificationStatus,
    parse_broadcast_head,
    verify_broadcast_head,
)


BODY = "# Team Broadcast\n\n<!-- broadcast-head: comment_id=30 comments=3 -->\n"


def test_parse_authoritative_marker():
    head = parse_broadcast_head(BODY)
    assert head.comment_id == 30
    assert head.comments == 3


@pytest.mark.parametrize(
    "body",
    [
        "# Team Broadcast\n",
        "<!-- broadcast-head: comment_id=x comments=3 -->",
        BODY + "<!-- broadcast-head: comment_id=31 comments=4 -->",
    ],
)
def test_marker_missing_malformed_or_duplicate_fails_closed(body):
    result = verify_broadcast_head(body, [10, 20, 30])
    assert result.status is BroadcastVerificationStatus.UNVERIFIED


def test_verified_only_when_authoritative_head_exists_and_is_reached():
    result = verify_broadcast_head(BODY, [10, 20, 30])
    assert result.status is BroadcastVerificationStatus.VERIFIED
    assert result.head is not None
    assert result.head.comment_id == 30


@pytest.mark.parametrize(
    "ids",
    [
        [],
        [10, 20],
        [10, 20, 40],
        [10, 30, 40],
        [30, 20],
        [10, 30, 30],
        [10, True, 30],
    ],
)
def test_incomplete_truncated_or_inconsistent_evidence_is_unverified(ids):
    result = verify_broadcast_head(BODY, ids)
    assert result.status is BroadcastVerificationStatus.UNVERIFIED


def test_verifier_does_not_mutate_inputs():
    body = BODY
    ids = [10, 20, 30]
    verify_broadcast_head(body, ids)
    assert body == BODY
    assert ids == [10, 20, 30]
