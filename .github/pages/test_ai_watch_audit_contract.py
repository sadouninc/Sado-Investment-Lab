from pathlib import Path
import unittest


SITE = Path(__file__).with_name("site.html").read_text(encoding="utf-8")


class AiWatchAuditContractTests(unittest.TestCase):
    def test_issue_comments_are_not_limited_to_first_page(self):
        self.assertIn("const fetchIssuePage = (page)", SITE)
        self.assertIn("linkedPage(link, 'last')", SITE)
        self.assertIn("findLatestTrustedAudit(lastPage)", SITE)
        self.assertNotIn("fetch(issueCommentsUrl", SITE)

    def test_run_audit_requires_trusted_github_author(self):
        self.assertIn("const trustedAuditAuthors = new Set(['sadouninc'])", SITE)
        self.assertIn("const parseAuditComment = (comment)", SITE)
        self.assertIn("comment?.user?.login", SITE)
        self.assertIn("if (!trustedAuditAuthors.has(author)) return null", SITE)

    def test_future_run_is_fail_closed(self):
        self.assertIn("const maxFutureSkewMinutes = 5", SITE)
        self.assertIn("if (isTooFarFuture(audit.runAt))", SITE)
        self.assertIn("state: 'DEGRADED'", SITE)

    def test_api_failure_keeps_safe_status_fallback(self):
        self.assertIn("loadLatestIssueAudit().catch(loadStatusFallback)", SITE)
        self.assertIn("Monitoring status: UNKNOWN", SITE)


if __name__ == "__main__":
    unittest.main()
