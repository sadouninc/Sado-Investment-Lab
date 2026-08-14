from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("build_site.py")
SPEC = importlib.util.spec_from_file_location("build_site_0814", MODULE_PATH)
assert SPEC and SPEC.loader
build_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_site
SPEC.loader.exec_module(build_site)


def test_2026_08_14_is_discoverable_and_renders_confirmed_trades_only():
    entries = {
        entry.day.isoformat(): entry
        for entry in build_site.discover_journal_entries()
    }
    assert "2026-08-14" in entries

    page = build_site.build_journal_page(entries["2026-08-14"])
    public_page = page.split('<details class="source-journal">', 1)[0]

    assert public_page.count("さくらインターネット（3778）") == 1
    assert public_page.count("日機装（6376）") == 1
    assert "3,800円" in public_page
    assert "3,875円" in public_page

    # Pending orders remain evidence/context and must not appear as confirmed trade rows.
    assert "テラドローン（278A）" not in public_page
    assert "オンコリスバイオ（4588）" not in public_page
