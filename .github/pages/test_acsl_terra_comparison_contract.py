from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "03_Companies" / "Mobility" / "6232_ACSL_vs_278A_Terra_Drone.md"


class AcslTerraComparisonContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_owner_first_view_has_japanese_shared_axes_without_winner_score(self):
        for value in (
            "30秒で見る核心",
            "成長エンジン",
            "資本の使い方",
            "売上の質",
            "最大の上昇材料",
            "最大のリスク",
        ):
            self.assertIn(value, self.text)
        self.assertNotIn("勝者", self.text)
        self.assertNotIn("winner score", self.text.lower())

    def test_comparison_axes_are_mobile_readable_groups_not_long_table(self):
        comparison = self.text.split("## 同じ軸で比較", 1)[1].split("### 読み違え防止", 1)[0]
        self.assertNotIn("| 軸 | ACSL | Terra Drone |", comparison)
        self.assertEqual(comparison.count('<div class="content-grid">'), 5)
        for axis in ("成長エンジン", "資本の使い方", "売上の質", "最大の上昇材料", "最大のリスク"):
            self.assertIn(f"### {axis}", comparison)
        self.assertGreaterEqual(comparison.count("<strong>ACSL</strong>"), 5)
        self.assertGreaterEqual(comparison.count("<strong>Terra Drone</strong>"), 5)

    def test_japanese_first_copy_does_not_require_english_analysis_terms(self):
        first_view = self.text.split("## 30秒で見る核心", 1)[1].split("### 読み違え防止", 1)[0]
        for term in (
            "Revenue Quality",
            "Catalyst",
            "Risk",
            "order visibility",
            "recurring optionality",
            "UNPROVEN",
            "defense scale",
            "global footprint",
        ):
            self.assertNotIn(term, first_view)
        self.assertIn("無人機交通管理（UTM）", first_view)
        self.assertIn("未検証", first_view)

    def test_fail_closed_research_semantics_are_explicit_in_japanese(self):
        self.assertIn("未確認 / 未検証", self.text)
        self.assertIn("両社とも未検証", self.text)
        self.assertIn("政府資金が確認できたことと、自立した黒字企業になったことは同義ではありません", self.text)
        self.assertIn("数値・分類をこのページ側で再計算しません", self.text)
        self.assertIn("比較仮説の状態", self.text)

    def test_comparison_does_not_become_trade_authority(self):
        self.assertIn("勝敗、売買判断、推奨数量を生成しません", self.text)
        self.assertIn("投資判断・売買指示ではありません", self.text)

    def test_identity_and_primary_evidence_are_traceable(self):
        self.assertIn("ACSL（6232）", self.text)
        self.assertIn("Terra Drone（278A）", self.text)
        self.assertIn("https://www.acsl.co.jp/", self.text)
        self.assertIn("https://terra-drone.net/", self.text)
        self.assertIn("Sado-Investment-Lab/issues/467", self.text)


if __name__ == "__main__":
    unittest.main()
