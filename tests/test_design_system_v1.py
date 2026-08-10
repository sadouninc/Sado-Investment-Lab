from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / ".github" / "pages" / "design-system-v1.css"
FIXTURE = ROOT / ".github" / "pages" / "fixtures" / "design-system-v1.html"


def test_design_system_v1_files_exist() -> None:
    assert CSS.is_file()
    assert FIXTURE.is_file()


def test_semantic_tokens_are_centralized() -> None:
    css = CSS.read_text(encoding="utf-8")
    required_tokens = (
        "--sil-surface-canvas",
        "--sil-surface-panel",
        "--sil-text-primary",
        "--sil-text-muted",
        "--sil-border-subtle",
        "--sil-border-emphasis",
        "--sil-accent-primary",
        "--sil-accent-brass",
        "--sil-state-supportive",
        "--sil-state-challenging",
        "--sil-state-critical",
        "--sil-state-stale",
        "--sil-state-unavailable",
        "--sil-state-unknown",
        "--sil-scenario-bear",
        "--sil-scenario-base",
        "--sil-scenario-bull",
    )
    for token in required_tokens:
        assert token in css


def test_minimum_primitives_are_present() -> None:
    css = CSS.read_text(encoding="utf-8")
    fixture = FIXTURE.read_text(encoding="utf-8")
    primitives = (
        "sil-page-shell",
        "sil-page-header",
        "sil-summary-card",
        "sil-kpi",
        "sil-delta",
        "sil-status-chip",
        "sil-scenario-card",
        "sil-alert",
        "sil-evidence-link",
        "sil-disclosure",
        "sil-table-shell",
        "sil-chart-container",
    )
    for primitive in primitives:
        assert f".{primitive}" in css
        assert primitive in fixture


def test_fixture_covers_state_and_scenario_semantics() -> None:
    fixture = FIXTURE.read_text(encoding="utf-8")
    for state in ("normal", "stale", "unavailable", "unknown"):
        assert f'data-state="{state}"' in fixture
    for scenario in ("bear", "base", "bull"):
        assert f'data-scenario="{scenario}"' in fixture
    assert "120 → 138" in fixture
    assert "予想の根拠を見る" in fixture
    assert "as_of: 2026-08-11" in fixture


def test_status_semantics_are_not_color_only() -> None:
    css = CSS.read_text(encoding="utf-8")
    fixture = FIXTURE.read_text(encoding="utf-8")
    assert '.sil-status-chip[data-state="stale"]::before' in css
    assert '.sil-status-chip[data-state="unavailable"]::before' in css
    assert '.sil-status-chip[data-state="unknown"]::before' in css
    assert "STALE / 更新確認が必要" in fixture
    assert "UNAVAILABLE / データ未取得" in fixture
    assert "UNKNOWN / 未設定" in fixture


def test_scenario_and_system_namespaces_are_separate() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert "--sil-state-critical" in css
    assert "--sil-scenario-bear" in css
    assert "--sil-state-supportive" in css
    assert "--sil-scenario-bull" in css
    assert "--sil-state-critical: var(--sil-scenario-bear)" not in css
    assert "--sil-state-supportive: var(--sil-scenario-bull)" not in css


def test_mobile_reflow_and_focus_contract_exist() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert "@media (max-width: 48rem)" in css
    assert "grid-template-columns: 1fr" in css
    assert ":focus-visible" in css
    assert "outline: 3px solid var(--sil-accent-brass)" in css
