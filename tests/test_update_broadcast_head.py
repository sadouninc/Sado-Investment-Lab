from __future__ import annotations

import unittest

from scripts.update_broadcast_head import (
    BroadcastHeadMarkerError,
    replace_broadcast_head,
    render_marker,
)


class BroadcastHeadMarkerTest(unittest.TestCase):
    def test_replaces_only_marker(self) -> None:
        body = "header\n<!-- broadcast-head: comment_id=100 comments=3 -->\nfooter\n"
        updated = replace_broadcast_head(body, comment_id=200, comments=4)
        self.assertEqual(
            updated,
            "header\n<!-- broadcast-head: comment_id=200 comments=4 -->\nfooter\n",
        )

    def test_preserves_other_bytes(self) -> None:
        prefix = "# 📣 Team Broadcast\n\nCurrent Active Board\n"
        suffix = "\n\n履歴は削除しない。\n"
        body = prefix + "<!-- broadcast-head: comment_id=123 comments=57 -->" + suffix
        updated = replace_broadcast_head(body, comment_id=456, comments=58)
        self.assertTrue(updated.startswith(prefix))
        self.assertTrue(updated.endswith(suffix))

    def test_missing_marker_fails_closed(self) -> None:
        with self.assertRaises(BroadcastHeadMarkerError):
            replace_broadcast_head("no marker", comment_id=1, comments=1)

    def test_duplicate_marker_fails_closed(self) -> None:
        body = (
            "<!-- broadcast-head: comment_id=1 comments=1 -->\n"
            "<!-- broadcast-head: comment_id=2 comments=2 -->"
        )
        with self.assertRaises(BroadcastHeadMarkerError):
            replace_broadcast_head(body, comment_id=3, comments=3)

    def test_invalid_values_fail_closed(self) -> None:
        for comment_id in (0, -1, True):
            with self.subTest(comment_id=comment_id), self.assertRaises(BroadcastHeadMarkerError):
                render_marker(comment_id=comment_id, comments=1)
        for comments in (-1, True):
            with self.subTest(comments=comments), self.assertRaises(BroadcastHeadMarkerError):
                render_marker(comment_id=1, comments=comments)


if __name__ == "__main__":
    unittest.main()
