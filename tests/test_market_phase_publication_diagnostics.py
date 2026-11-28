import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.market_phase_publication_diagnostics import (
    EXPECTED_ROUTE,
    PLACEHOLDER_MARKER,
    check_artifact,
    diagnose,
    main,
)

ROOT = Path(__file__).resolve().parents[1]


def artifact(**over):
    data = {
        "schema_version": 1,
        "universe": {"id": "synthetic", "name": "Synthetic", "requested": 2},
        "generated_at": "2099-01-10T00:00:00+00:00",
        "symbols": [{"code": "AAA", "group": "G1"}, {"code": "BBB", "group": "G2"}],
        "clusters": {"AAA": 0, "BBB": 1},
        "data_quality": {
            "included": 2,
            "excluded": [{"code": "CCC", "reason": "price_file_missing"}],
            "symbols": {"AAA": {"end": "2099-01-09"}, "BBB": {"end": "2099-01-09"}},
        },
    }
    data.update(over)
    return data


def full_page(route=EXPECTED_ROUTE, drop=()):
    body = [
        "# Sado Market Phase Analyzer",
        "## 正規化比較チャート",
        "## 相関ヒートマップ",
        "## 先行・遅行候補",
        '<script type="application/json" id="phase-data">{}</script>',
    ]
    body = [line for line in body if not any(d in line for d in drop)]
    return f"---\nlayout: site\npermalink: {route}\n---\n\n" + "\n".join(body) + "\n"


def placeholder_page():
    return (
        f"---\nlayout: site\npermalink: {EXPECTED_ROUTE}\n---\n\n# Sado Market Phase Analyzer\n\n"
        f'<div class="notice-card"><strong>{PLACEHOLDER_MARKER}。</strong></div>\n'
    )


def codes(r):
    return [f["code"] for f in r["findings"]]


def test_ok():
    r = diagnose(artifact_text=json.dumps(artifact()), page_text=full_page(),
                 price_manifest={"AAA": "2099-01-09", "BBB": "2099-01-08", "CCC": "2099-01-09"})
    assert r["primary"] == "OK"
    assert r["publishable"] is True
    assert r["findings"] == []
    assert r["cause_asserted"] is False
    assert r["artifact_state"] == "valid" and r["page_state"] == "full"


def test_not_generated_with_expected_placeholder():
    r = diagnose(artifact_text=None, page_text=placeholder_page())
    assert r["primary"] == "ARTIFACT_NOT_GENERATED"
    assert r["page_state"] == "placeholder"
    assert "PAGE_PLACEHOLDER_WITH_ARTIFACT" not in codes(r)


def test_page_not_built_takes_precedence():
    r = diagnose(artifact_text=None, page_text=None)
    assert r["primary"] == "PAGE_NOT_BUILT"
    assert set(codes(r)) == {"PAGE_NOT_BUILT", "ARTIFACT_NOT_GENERATED"}


def test_build_order_placeholder_despite_artifact():
    r = diagnose(artifact_text=json.dumps(artifact()), page_text=placeholder_page())
    assert r["primary"] == "PAGE_PLACEHOLDER_WITH_ARTIFACT"


@pytest.mark.parametrize("text", ["", "{", "[]", "null", '"x"'])
def test_artifact_not_json_object(text):
    r = diagnose(artifact_text=text, page_text=full_page())
    assert r["primary"] == "ARTIFACT_MALFORMED"
    assert r["artifact_state"] == "invalid"


@pytest.mark.parametrize(
    "over",
    [
        {"generated_at": None},
        {"generated_at": "soon"},
        {"universe": {"requested": "2"}},
        {"data_quality": {"included": True, "excluded": []}},
        {"data_quality": {"included": 2, "excluded": {}}},
        {"data_quality": {"included": 2, "excluded": [], "symbols": []}},
        {"clusters": []},
        {"symbols": [{"code": "AAA"}]},
        {"symbols": "AAA"},
    ],
)
def test_artifact_contract_fields(over):
    report, problems = check_artifact(json.dumps(artifact(**over)))
    assert report is None and problems
    assert diagnose(artifact_text=json.dumps(artifact(**over)), page_text=full_page())["primary"] == "ARTIFACT_MALFORMED"


def test_schema_version_mismatch():
    r = diagnose(artifact_text=json.dumps(artifact(schema_version=2)), page_text=full_page())
    assert r["primary"] == "ARTIFACT_SCHEMA_MISMATCH"


def test_stale_artifact_newer_price_and_missing_symbol():
    r = diagnose(artifact_text=json.dumps(artifact()), page_text=full_page(),
                 price_manifest={"AAA": "2099-01-12", "BBB": "2099-01-09", "DDD": "2099-01-09"})
    assert r["primary"] == "ARTIFACT_STALE"
    details = [f["detail"] for f in r["findings"]]
    assert any(d.startswith("AAA:") for d in details)
    assert any(d.startswith("DDD:") for d in details)
    assert not any(d.startswith("BBB:") for d in details)


def test_excluded_symbol_not_stale_and_bad_manifest_date():
    r = diagnose(artifact_text=json.dumps(artifact()), page_text=full_page(),
                 price_manifest={"CCC": "2099-02-01", "AAA": "not-a-date"})
    assert codes(r) == ["ARTIFACT_STALE"]
    assert "unreadable" in r["findings"][0]["detail"]


def test_manifest_not_mapping():
    r = diagnose(artifact_text=json.dumps(artifact()), page_text=full_page(), price_manifest=["AAA"])
    assert r["primary"] == "ARTIFACT_STALE"


def test_route_mismatch_and_missing_front_matter():
    assert diagnose(artifact_text=json.dumps(artifact()), page_text=full_page(route="/research/old/"))["primary"] == "ROUTE_MISMATCH"
    assert diagnose(artifact_text=json.dumps(artifact()), page_text="# Sado Market Phase Analyzer")["primary"] == "ROUTE_MISMATCH"


def test_page_sections_missing():
    r = diagnose(artifact_text=json.dumps(artifact()), page_text=full_page(drop=("相関ヒートマップ",)))
    assert r["primary"] == "PAGE_SECTIONS_MISSING"
    assert "相関ヒートマップ" in r["findings"][0]["detail"]
    assert r["page_state"] == "incomplete"


def test_deterministic():
    kwargs = dict(artifact_text="{", page_text=None, price_manifest=None)
    assert json.dumps(diagnose(**kwargs), sort_keys=True) == json.dumps(diagnose(**kwargs), sort_keys=True)


def _load_build_site(monkeypatch):
    path = ROOT / ".github" / "pages" / "build_site.py"
    spec = importlib.util.spec_from_file_location("build_site_for_diag", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


def test_contract_matches_real_build_site_with_synthetic_artifact(tmp_path, monkeypatch):
    """The markers and placeholder used here must match what build_site really writes."""
    build_site = _load_build_site(monkeypatch)
    monkeypatch.setattr(build_site, "SITE", tmp_path / "site")
    data_path = tmp_path / "ai-semiconductor.json"
    monkeypatch.setattr(build_site, "MARKET_PHASE_DATA", data_path)
    page_path = tmp_path / "site" / "research" / "market-phase" / "ai-semiconductor" / "index.md"

    build_site.build_market_phase()  # artifact absent -> placeholder
    r = diagnose(artifact_text=None, page_text=page_path.read_text(encoding="utf-8"))
    assert r["primary"] == "ARTIFACT_NOT_GENERATED"
    assert r["page_state"] == "placeholder"

    data_path.write_text(json.dumps(artifact()), encoding="utf-8")
    r = diagnose(artifact_text=data_path.read_text(encoding="utf-8"), page_text=page_path.read_text(encoding="utf-8"))
    assert r["primary"] == "PAGE_PLACEHOLDER_WITH_ARTIFACT"

    build_site.build_market_phase()
    r = diagnose(artifact_text=data_path.read_text(encoding="utf-8"), page_text=page_path.read_text(encoding="utf-8"))
    assert r["primary"] == "OK", r["findings"]


def test_cli(tmp_path):
    art, page = tmp_path / "a.json", tmp_path / "p.md"
    page.write_text(placeholder_page(), encoding="utf-8")
    assert main(["--artifact", str(art), "--page", str(page)]) == 1
    art.write_text(json.dumps(artifact()), encoding="utf-8")
    page.write_text(full_page(), encoding="utf-8")
    out = tmp_path / "o.json"
    assert main(["--artifact", str(art), "--page", str(page), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["primary"] == "OK"
    bad = tmp_path / "m.json"
    bad.write_text("{", encoding="utf-8")
    assert main(["--artifact", str(art), "--page", str(page), "--price-manifest", str(bad)]) == 2


def test_cli_module(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.market_phase_publication_diagnostics",
         "--artifact", str(tmp_path / "none.json"), "--page", str(tmp_path / "none.md")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 1, proc.stderr
    assert json.loads(proc.stdout)["primary"] == "PAGE_NOT_BUILT"
