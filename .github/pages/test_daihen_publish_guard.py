from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("build_risk_preflight_guard", HERE / "build_risk_preflight.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DaihenPublishGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_site = MODULE.SITE
        self.temp = tempfile.TemporaryDirectory()
        MODULE.SITE = Path(self.temp.name)

    def tearDown(self) -> None:
        MODULE.SITE = self.original_site
        self.temp.cleanup()

    def _write_valid_artifact(self) -> None:
        home = MODULE.SITE / "index.md"
        home.parent.mkdir(parents=True, exist_ok=True)
        home.write_text(
            "ダイヘン 投資判断コックピット\n"
            "{{ '/decision-cockpit/daihen/' | relative_url }}\n",
            encoding="utf-8",
        )
        cockpit = MODULE.SITE / "decision-cockpit" / "daihen" / "index.md"
        cockpit.parent.mkdir(parents=True, exist_ok=True)
        cockpit.write_text(
            "---\npermalink: /decision-cockpit/daihen/\n---\n"
            "この画面は売買指示を生成しません。\n",
            encoding="utf-8",
        )

    def test_accepts_visible_home_entry_and_cockpit(self) -> None:
        self._write_valid_artifact()
        MODULE.verify_daihen_publish_contract()

    def test_fails_when_home_entry_is_missing(self) -> None:
        self._write_valid_artifact()
        (MODULE.SITE / "index.md").write_text("Home only\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Home entry missing"):
            MODULE.verify_daihen_publish_contract()

    def test_fails_when_cockpit_is_missing(self) -> None:
        home = MODULE.SITE / "index.md"
        home.write_text(
            "ダイヘン 投資判断コックピット /decision-cockpit/daihen/\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "cockpit page is missing"):
            MODULE.verify_daihen_publish_contract()


if __name__ == "__main__":
    unittest.main()
