from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site-src/concepts/investment-decision-cockpit/index.md"


def test_cockpit_guide_prioritizes_user_first_view_before_internal_contract():
    page = PAGE.read_text(encoding="utf-8")
    title = page.index("<h1>投資判断コックピット</h1>")
    first_checks = page.index("最初の30秒で見る3点")
    internal = page.index("Concept contract: #313 / #317 / #312 / #320")
    assert title < first_checks < internal
    assert "Investment Decision Cockpit — 見方ガイド</h1>" not in page
    assert "<summary>設計・実装情報</summary>" in page
