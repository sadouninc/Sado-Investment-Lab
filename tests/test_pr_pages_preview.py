import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "pages" / "prepare_pr_preview.py"
SPEC = importlib.util.spec_from_file_location("prepare_pr_preview", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PullRequestPagesPreviewTest(unittest.TestCase):
    def test_prepares_isolated_browser_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "companies" / "semiconductor" / "4063-shinetsu"
            nested.mkdir(parents=True)
            (root / "index.html").write_text(
                '<html><body><a href="/Sado-Investment-Lab/framework/">Framework</a>'
                '<a href="/Sado-Investment-Lab/assets/site.css">CSS</a>'
                '<a href="https://example.com/">External</a></body></html>',
                encoding="utf-8",
            )
            (nested / "index.html").write_text("<html><body>Shin-Etsu</body></html>", encoding="utf-8")

            metadata = MODULE.prepare_preview(
                root,
                owner="sadouninc",
                repo="Sado-Investment-Lab",
                ref="pages-previews",
                namespace="pr-345",
                pr_number=345,
                head_sha="0123456789abcdef",
                built_at="2026-08-12T00:00:00Z",
            )

            html = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn("PR PREVIEW · #345 · NOT PRODUCTION", html)
            self.assertIn("Head 0123456789ab", html)
            self.assertIn(
                'href="/sadouninc/Sado-Investment-Lab/pages-previews/pr-345/framework/index.html"',
                html,
            )
            self.assertIn(
                'href="/sadouninc/Sado-Investment-Lab/pages-previews/pr-345/assets/site.css"',
                html,
            )
            self.assertIn('href="https://example.com/"', html)
            self.assertEqual(metadata["head_sha"], "0123456789abcdef")
            saved = json.loads((root / "preview-metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(saved["not_production"])
            self.assertEqual(saved["html_files"], 2)

    def test_rewrite_preserves_external_and_inert_content(self):
        prefix = "/sadouninc/Sado-Investment-Lab/pages-previews/pr-870/"
        source = (
            '<a href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867">GitHub</a>'
            '<a href="/Sado-Investment-Lab/framework/">Internal</a>'
            "<img src=/Sado-Investment-Lab/assets/site.css />"
            '<div data-x=\'href="/Sado-Investment-Lab/"\'>Data</div>'
            '<a title="2 > 1" href="/Sado-Investment-Lab/themes/?x=1#top">Theme</a>'
            '<script>const x = \'href="/Sado-Investment-Lab/"\';</script>'
            '<style>.x{background:url("/Sado-Investment-Lab/a.png")}</style>'
            '<a href="//github.com/sadouninc/Sado-Investment-Lab/issues/867">Protocol</a>'
        )

        rewritten = MODULE.rewrite_html(
            source,
            production_base="/Sado-Investment-Lab/",
            prefix=prefix,
            pr_number=870,
            head_sha="e6e46f3f05e6",
            built_at="2026-10-31T00:00:00Z",
        )

        self.assertIn(
            'href="https://github.com/sadouninc/Sado-Investment-Lab/issues/867"',
            rewritten,
        )
        self.assertIn(
            f'href="{prefix}framework/index.html"',
            rewritten,
        )
        self.assertIn(
            f"src={prefix}assets/site.css",
            rewritten,
        )
        self.assertIn(
            'data-x=\'href="/Sado-Investment-Lab/"\'',
            rewritten,
        )
        self.assertIn(
            f'href="{prefix}themes/index.html?x=1#top"',
            rewritten,
        )
        self.assertIn(
            '<script>const x = \'href="/Sado-Investment-Lab/"\';</script>',
            rewritten,
        )
        self.assertIn(
            '<style>.x{background:url("/Sado-Investment-Lab/a.png")}</style>',
            rewritten,
        )
        self.assertIn(
            'href="//github.com/sadouninc/Sado-Investment-Lab/issues/867"',
            rewritten,
        )

        second_pass = MODULE.rewrite_html(
            rewritten,
            production_base="/Sado-Investment-Lab/",
            prefix=prefix,
            pr_number=870,
            head_sha="e6e46f3f05e6",
            built_at="2026-10-31T00:00:00Z",
        )
        self.assertEqual(second_pass, rewritten)

    def test_malformed_start_tag_fails_closed(self):
        source = '<a href="/Sado-Investment-Lab/framework/"'
        rewritten = MODULE._rewrite_url_attributes(
            source,
            production_base="/Sado-Investment-Lab/",
            prefix="/sadouninc/Sado-Investment-Lab/pages-previews/pr-870/",
        )
        self.assertEqual(rewritten, source)

    def test_workflow_keeps_production_deploy_separate(self):
        workflow = (ROOT / ".github" / "workflows" / "publish-site.yml").read_text(encoding="utf-8")
        self.assertIn("if: github.event_name != 'pull_request'", workflow)
        self.assertIn("preview:", workflow)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", workflow)
        self.assertIn("publish_branch: pages-previews", workflow)
        self.assertIn("destination_dir: pr-${{ github.event.pull_request.number }}", workflow)
        preview_section = workflow.split("\n  preview:", 1)[1].split("\n  deploy:", 1)[0]
        self.assertNotIn("environment:", preview_section)
        self.assertNotIn("actions/deploy-pages", preview_section)


if __name__ == "__main__":
    unittest.main()
