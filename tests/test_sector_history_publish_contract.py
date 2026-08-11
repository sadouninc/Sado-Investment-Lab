from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = ROOT / ".gitignore"
MONEY_FLOW_WORKFLOW = ROOT / ".github" / "workflows" / "money-flow-canonical.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "publish-site.yml"
SECTOR_HISTORY = "data/generated/public/money-flow/sector-history.jsonl"


def test_sector_history_is_explicitly_versionable_canonical_artifact() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")
    assert f"!{SECTOR_HISTORY}" in text


def test_canonical_workflow_persists_sector_history_when_generated() -> None:
    text = MONEY_FLOW_WORKFLOW.read_text(encoding="utf-8")
    assert f"if [ -f {SECTOR_HISTORY} ]; then" in text
    assert f"git add {SECTOR_HISTORY}" in text


def test_sector_history_commit_republishes_pages() -> None:
    text = PAGES_WORKFLOW.read_text(encoding="utf-8")
    assert '"data/generated/public/money-flow/**"' in text


def test_pages_home_supply_uses_existing_provider_not_fake_fixture() -> None:
    text = (ROOT / ".github" / "pages" / "enrich_home_today.py").read_text(encoding="utf-8")
    assert "SectorRotationProvider().collect()" in text
    assert "sampleSnapshots" not in text
    assert "DEMO_" not in text
