from datetime import datetime, timezone

from scripts.developing_signal_store import StoreReadResult

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / ".github" / "pages" / "build_developing_signals.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_developing_signals", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("builder unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signal(**overrides):
    base = {
        "signal_id": "signal:test:2026-08-13:abc",
        "signal_key": "test",
        "title": "AI/DC設備投資の先行兆候",
        "status": "STRENGTHENING",
        "direction": "STRENGTHENING",
        "summary": "受注へ近づく兆候を継続確認する。",
        "why_it_may_matter": "Company Researchへ昇格する前に利益Transmissionを確認するため。",
        "last_observed_at": "2026-08-12T00:00:00+00:00",
        "next_checkpoint": None,
        "checkpoint_reason": "次回決算で受注を確認する。",
        "related_entities": [{"type": "THEME", "id": "AI_DC"}],
        "source_refs": ["primary:test"],
        "observations": [{"observed_at": "2026-08-12T00:00:00+00:00", "observation": "一次Evidenceを確認。"}],
    }
    base.update(overrides)
    return base


def test_owner_hierarchy_and_non_trade_boundary():
    builder = load_builder()
    page = builder.render(
        StoreReadResult("OK", (signal(),), ()),
        now=datetime(2026, 8, 13, tzinfo=timezone.utc),
    )
    assert "Active WATCH: 1" in page
    assert "↑ 強まっている" in page
    assert "AI/DC設備投資の先行兆候" in page
    assert "なぜ見るか" in page
    assert "関連" in page
    assert "最終観測 1日前" in page
    assert "次回決算で受注を確認する" in page
    assert "BUY / SELL推奨ではありません" in page
    assert "観測履歴・Source" in page


def test_unknown_direction_is_not_rendered_as_negative():
    builder = load_builder()
    page = builder.render(StoreReadResult("OK", (signal(direction="UNKNOWN", status="WATCHING"),), ()))
    assert "? 方向不明" in page
    assert "UNKNOWNはnegativeへ丸めません" in page
    assert "SELL推奨" in page


def test_future_last_observed_at_fails_closed():
    builder = load_builder()
    page = builder.render(
        StoreReadResult(
            "OK",
            (signal(last_observed_at="2026-08-14T00:00:00+00:00"),),
            (),
        ),
        now=datetime(2026, 8, 13, tzinfo=timezone.utc),
    )
    assert "最終観測 UNKNOWN — future timestamp" in page
    assert "最終観測 0日前" not in page


def test_naive_last_observed_at_fails_closed():
    builder = load_builder()
    page = builder.render(
        StoreReadResult("OK", (signal(last_observed_at="2026-08-12T00:00:00"),), ()),
        now=datetime(2026, 8, 13, tzinfo=timezone.utc),
    )
    assert "最終観測 UNKNOWN — timezone未設定" in page


def test_terminal_signal_is_not_in_active_watch():
    builder = load_builder()
    page = builder.render(StoreReadResult("OK", (signal(status="PROMOTED"),), ()))
    assert "Active WATCH: 0" in page
    assert "Active WATCHはありません" in page
    assert "AI/DC設備投資の先行兆候" not in page


def test_partial_store_fails_closed_without_inventing_signal():
    builder = load_builder()
    page = builder.render(StoreReadResult("PARTIAL", (), ("line 2 invalid",)))
    assert "Data status: PARTIAL" in page
    assert "line 2 invalid" in page
    assert "欠損を正常値・negative signalへ変換しません" in page
    assert "Active WATCH: 0" in page


def test_standalone_builder_generates_canonical_route_source(tmp_path, monkeypatch):
    builder = load_builder()
    expected = StoreReadResult("OK", (signal(),), ())
    monkeypatch.setattr(builder, "read_store", lambda _path: expected)

    target = tmp_path / "research" / "developing-signals" / "index.md"
    generated = builder.build(target)
    page = generated.read_text(encoding="utf-8")

    assert generated == target
    assert "permalink: /research/developing-signals/" in page
    assert "Active WATCH: 1" in page
    assert "AI/DC設備投資の先行兆候" in page


def test_builder_consumes_canonical_reader_only():
    text = BUILDER.read_text(encoding="utf-8")
    assert "from scripts.developing_signal_store import" in text
    assert "read_store(" in text
    assert "developing-signals.jsonl" in text
    assert "write_signal(" not in text
    assert "BUY / SELL推奨ではありません" in text
