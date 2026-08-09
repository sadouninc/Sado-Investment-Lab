from __future__ import annotations

import unittest

from scripts.cockpit_ref_resolver import (
    DAIHEN_RESEARCH_ROUTE,
    first_resolved_href,
    resolve_cockpit_ref,
)


class CockpitRefResolverTests(unittest.TestCase):
    def test_company_research_uses_known_stable_daihen_route(self):
        resolved = resolve_cockpit_ref("company-research:6622:2026-08-09")
        self.assertEqual(resolved.href, DAIHEN_RESEARCH_ROUTE)
        self.assertEqual(resolved.kind, "COMPANY_RESEARCH")

    def test_issue_ref_uses_explicit_github_issue_url(self):
        resolved = resolve_cockpit_ref("issue:214")
        self.assertEqual(
            resolved.href,
            "https://github.com/sadouninc/Sado-Investment-Lab/issues/214",
        )

    def test_unrouted_canonical_refs_do_not_guess_pages(self):
        for ref in (
            "forward-per:6622:FY2027:2026-07-29",
            "hypothesis:6622:FY2027",
            "decision:6622:latest",
            "decision-snapshot:6622:latest:immutable",
            "decision-comparison:6622:current-vs-latest",
            "episode:6622:current",
        ):
            with self.subTest(ref=ref):
                resolved = resolve_cockpit_ref(ref)
                self.assertIsNone(resolved.href)
                self.assertEqual(resolved.kind, "CANONICAL_UNROUTED")

    def test_other_security_research_does_not_route_to_daihen(self):
        resolved = resolve_cockpit_ref("company-research:4063:2026-08-09")
        self.assertIsNone(resolved.href)

    def test_first_resolved_href_skips_unrouted_refs(self):
        href = first_resolved_href(
            [
                "forward-per:6622:FY2027:2026-07-29",
                "company-research:6622:2026-08-09",
            ]
        )
        self.assertEqual(href, DAIHEN_RESEARCH_ROUTE)


if __name__ == "__main__":
    unittest.main()
