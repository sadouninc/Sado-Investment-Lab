from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scripts.cockpit_ref_resolver import first_resolved_href


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "site-src" / "decision-cockpit" / "daihen" / "index.md"
CONCEPT_GUIDE_ROUTE = "/concepts/investment-decision-cockpit/"
CONCEPT_GUIDE_SOURCE = ROOT / "site-src" / "concepts" / "investment-decision-cockpit" / "index.md"
START = "<!-- cockpit-drilldown:start -->"
END = "<!-- cockpit-drilldown:end -->"


def _cta(label: str, refs: object, *, unavailable_text: str) -> str:
    href = first_resolved_href(refs)
    if href:
        return f"[{label}]({{{{ '{href}' | relative_url }}}})" if href.startswith("/") else f"[{label}]({href})"
    return f'<span class="muted">{unavailable_text}</span>'


def _refs_with_prefix(refs: object, prefix: str) -> list[str]:
    return [str(ref) for ref in list(refs or []) if str(ref).startswith(prefix)]


def _concept_help_link() -> str:
    if not CONCEPT_GUIDE_SOURCE.is_file():
        return '<span class="muted">見方ガイドは現在利用できません</span>'
    return (
        "[この画面の見方・判断コックピットの読み方]"
        f"({{{{ '{CONCEPT_GUIDE_ROUTE}' | relative_url }}}})"
    )


def _block(model: Mapping[str, Any]) -> str:
    earnings = model["earnings_driver"]
    valuation = model["valuation"]
    hypothesis = model["hypothesis"]
    history = model["decision_history"]

    earnings_refs = list(earnings.get("driver_refs") or []) + list(earnings.get("source_refs") or [])
    # Do not silently fall back from a dedicated Forward PER ref to generic
    # Company Research. If the dedicated route does not exist, show that fact.
    valuation_refs = _refs_with_prefix(valuation.get("source_refs"), "forward-per:6622:")
    hypothesis_refs = list(hypothesis.get("source_refs") or [])
    history_refs = list(history.get("source_refs") or [])

    return "\n".join(
        [
            START,
            "## 🔎 根拠へ降りる",
            "",
            "疑問が生じた箇所から、存在が確認できるCanonical詳細だけへ移動します。未生成routeは推測しません。",
            "",
            "- 画面の見方: " + _concept_help_link(),
            "- 利益予想の根拠: " + _cta("ダイヘン企業研究を開く", earnings_refs, unavailable_text="詳細ページ未生成"),
            "- Valuationの根拠: " + _cta("Forward PER詳細を開く", valuation_refs, unavailable_text="Forward PER専用ページはまだありません。Canonical refは画面内に保持しています"),
            "- 投資仮説: " + _cta("仮説詳細を開く", hypothesis_refs, unavailable_text="仮説専用ページはまだありません。Canonical refは画面内に保持しています"),
            "- 過去判断: " + _cta("Decision Historyを開く", history_refs, unavailable_text="Decision History専用ページはまだありません。historical snapshot refは画面内に保持しています"),
            "",
            END,
        ]
    )


def enhance_page(page: str, model: Mapping[str, Any]) -> str:
    if START in page or END in page:
        if page.count(START) != 1 or page.count(END) != 1:
            raise ValueError("invalid cockpit drilldown marker state")
        before, rest = page.split(START, 1)
        _, after = rest.split(END, 1)
        page = before.rstrip() + "\n\n" + after.lstrip()

    # Keep the enhancer compatible with both legacy blank-line spacing and
    # the current builder's compact separator before the 30-second checklist.
    anchors = ("\n---\n\n## 30秒チェック", "\n---\n## 30秒チェック")
    anchor = next((candidate for candidate in anchors if candidate in page), None)
    if anchor is None:
        raise ValueError("cockpit 30-second anchor not found")
    return page.replace(anchor, "\n\n" + _block(model) + anchor, 1)


def enhance_file(model: Mapping[str, Any]) -> None:
    if not TARGET.is_file():
        raise FileNotFoundError(TARGET)
    page = TARGET.read_text(encoding="utf-8")
    TARGET.write_text(enhance_page(page, model).rstrip() + "\n", encoding="utf-8")
