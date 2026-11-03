from pathlib import Path
import json
import subprocess
import unittest


SITE = Path(__file__).with_name("site.html").read_text(encoding="utf-8")
CONTRACT = SITE.split("// AI_WATCH_CONTRACT_START", 1)[1].split(
    "// AI_WATCH_CONTRACT_END", 1
)[0]


def run_contract(expression: str):
    prelude = """
const trustedAuditAuthors = new Set(['sadouninc']);
const staleAfterMinutes = 150;
const maxFutureSkewMinutes = 5;
Date.now = () => new Date('2026-11-03T12:00:00Z').getTime();
"""
    result = subprocess.run(
        ["node", "-e", prelude + CONTRACT + "\nconsole.log(JSON.stringify(" + expression + "));"],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def status_payload(
    *,
    run_at="2026-11-03T11:55:00Z",
    success_at="2026-11-03T11:55:00Z",
    status="OK",
    delta=0,
    persisted=False,
    persistence="NOT_REQUIRED",
):
    return {
        "last_run_at": run_at,
        "last_success_at": success_at,
        "last_news_delta_at": None,
        "last_status": status,
        "news_delta": delta,
        "news_persisted": persisted,
        "persistence_status": persistence,
        "stale_after_minutes": 150,
    }


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


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
        result = run_contract(
            "classifyAudit({runAt:new Date('2026-11-03T12:06:00Z'),"
            "status:'OK',newsDelta:0,newsPersisted:false,persistenceStatus:'NOT_REQUIRED'})"
        )
        self.assertEqual("DEGRADED", result["state"])

    def test_api_failure_keeps_safe_unknown_state(self):
        self.assertIn("Promise.allSettled([loadLatestIssueAudit(), loadStatusFile()])", SITE)
        self.assertIn("Monitoring status: UNKNOWN", SITE)

    def test_new_status_wins_over_stale_issue_audit(self):
        payload = status_payload()
        result = run_contract(
            "selectMonitoringSource("
            "{runAt:new Date('2026-09-25T00:30:00+09:00'),status:'OK',newsDelta:0,"
            "newsPersisted:false,persistenceStatus:'NOT_REQUIRED'},"
            + js(payload)
            + ")"
        )
        self.assertEqual("status", result["kind"])
        self.assertEqual("HEALTHY", result["health"]["state"])

    def test_new_error_audit_is_not_hidden_by_old_ok_status(self):
        payload = status_payload(
            run_at="2026-11-03T10:00:00Z",
            success_at="2026-11-03T10:00:00Z",
        )
        result = run_contract(
            "selectMonitoringSource("
            "{runAt:new Date('2026-11-03T11:58:00Z'),status:'ERROR',newsDelta:0,"
            "newsPersisted:false,persistenceStatus:'NOT_REQUIRED'},"
            + js(payload)
            + ")"
        )
        self.assertEqual("audit", result["kind"])
        self.assertEqual("DEGRADED", result["health"]["state"])

    def test_both_stale_sources_remain_fail_closed(self):
        payload = status_payload(
            run_at="2026-11-03T01:00:00Z",
            success_at="2026-11-03T01:00:00Z",
        )
        result = run_contract(
            "selectMonitoringSource("
            "{runAt:new Date('2026-11-03T00:00:00Z'),status:'OK',newsDelta:0,"
            "newsPersisted:false,persistenceStatus:'NOT_REQUIRED'},"
            + js(payload)
            + ")"
        )
        self.assertEqual("STALE", result["health"]["state"])

    def test_unknown_and_invalid_enums_never_render_healthy(self):
        for field, value in (
            ("last_status", "UNKNOWN"),
            ("last_status", "BOGUS"),
            ("persistence_status", "BOGUS"),
        ):
            with self.subTest(field=field, value=value):
                payload = status_payload()
                payload[field] = value
                result = run_contract("classifyStatusFile(" + js(payload) + ")")
                self.assertNotEqual("HEALTHY", result["state"])

    def test_invalid_delta_and_persistence_combinations_fail_closed(self):
        cases = [
            {"news_delta": -1},
            {"news_delta": 1, "news_persisted": False, "persistence_status": "COMPLETED"},
            {"news_delta": 1, "news_persisted": False, "persistence_status": "NOT_REQUIRED"},
            {"news_delta": 0, "news_persisted": True, "persistence_status": "COMPLETED"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                payload = status_payload()
                payload.update(changes)
                result = run_contract("classifyStatusFile(" + js(payload) + ")")
                self.assertEqual("DEGRADED", result["state"])

    def test_invalid_timestamps_and_order_fail_closed(self):
        payload = status_payload(
            run_at="2026-11-03T11:00:00Z",
            success_at="2026-11-03T11:30:00Z",
        )
        result = run_contract("classifyStatusFile(" + js(payload) + ")")
        self.assertEqual("DEGRADED", result["state"])

        payload["last_run_at"] = "not-a-date"
        result = run_contract("classifyStatusFile(" + js(payload) + ")")
        self.assertEqual("UNKNOWN", result["state"])


if __name__ == "__main__":
    unittest.main()
