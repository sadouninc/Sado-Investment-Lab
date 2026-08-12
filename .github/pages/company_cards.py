from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path


UPDATED = re.compile(r"^\s*(?:>\s*)?(?:Updated|更新日)[:：]\s*(.+?)\s*$", re.MULTILINE)
HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TITLE = re.compile(r"^#\s+.+?\s*$", re.MULTILINE)
STRONG_WATCH_TITLE = "AI/DC Strong Watch 3"
STRONG_WATCH_SOURCE = "AI_DC_Strong_Watch.md"
STRONG_WATCH_STATE = "状態: `STRONG_WATCH / ENTRY_REVIEW`"


@dataclass(frozen=True)
class CompanyCardSummary:
    title: str
    category: str
    source_name: str
    freshness: str | None
    sections: tuple[str, ...]
    content: str = ""


def summarize_company(title: str, category: str, source: Path, content: str) -> CompanyCardSummary:
    updated = UPDATED.search(content)
    sections = tuple(dict.fromkeys(match.group(1).strip() for match in HEADING.finditer(content)))
    return CompanyCardSummary(
        title=title,
        category=category,
        source_name=source.name,
        freshness=updated.group(1).strip() if updated else None,
        sections=sections,
        content=content,
    )


def _markdown_table_rows(content: str, section: str) -> list[dict[str, str]]:
    match = re.search(
        rf"^##\s+{re.escape(section)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []
    table_lines = [line.strip() for line in match.group("body").splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return []

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip("|").split("|")]

    headers = cells(table_lines[0])
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        values = cells(line)
        if len(values) != len(headers):
            continue
        rows.append(dict(zip(headers, values)))
    return rows


def _plain_markdown(value: str) -> str:
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    return value.strip()


def _is_strong_watch_summary(summary: CompanyCardSummary) -> bool:
    return (
        summary.source_name == STRONG_WATCH_SOURCE
        or STRONG_WATCH_STATE in summary.content
        or STRONG_WATCH_TITLE in summary.title
    )


def _is_strong_watch_content(content: str) -> bool:
    return STRONG_WATCH_STATE in content or STRONG_WATCH_TITLE in content


def _render_strong_watch_summary(summary: CompanyCardSummary) -> str:
    freshness = html.escape(summary.freshness) if summary.freshness else "更新日未記録"
    freshness_state = "normal" if summary.freshness else "unavailable"
    rows = _markdown_table_rows(summary.content, "3社比較")
    cards: list[str] = []
    anchors = {"5805": "watch-5805", "6504": "watch-6504", "6622": "watch-6622"}
    for row in rows:
        company = _plain_markdown(row.get("銘柄", "UNKNOWN"))
        code = company.split()[0] if company else ""
        why = _plain_markdown(row.get("Why Watching", "UNKNOWN"))
        evidence = _plain_markdown(row.get("Evidence Stage", "UNKNOWN"))
        gap = _plain_markdown(row.get("Expectation Gap", "UNKNOWN"))
        quality = _plain_markdown(row.get("Fundamental Quality", "UNKNOWN"))
        anchor = anchors.get(code, "company-detail")
        cards.append(
            '<article class="codex-summary-card strong-watch-card">'
            f'<span class="codex-card-question">{html.escape(company)}</span>'
            f'<h2>{html.escape(why)}</h2>'
            f'<p><strong>Evidence:</strong> {html.escape(evidence)}</p>'
            '<div class="codex-page-header__meta">'
            f'<span class="codex-status-chip" data-state="normal">Gap: {html.escape(gap)}</span>'
            f'<span class="codex-status-chip" data-state="normal">Quality: {html.escape(quality)}</span>'
            '</div>'
            f'<a class="codex-action codex-action--secondary" href="#{anchor}">Trigger / Risk / Checkpoint</a>'
            '</article>'
        )

    if not cards:
        cards.append(
            '<article class="codex-summary-card">'
            '<span class="codex-card-question">Comparison</span>'
            '<span class="codex-status-chip" data-state="unavailable">比較データを取得できません</span>'
            '<h2>UNKNOWN</h2><p>Research projectionを推測で補完しません。</p>'
            '</article>'
        )

    return (
        '<section class="codex-page-shell company-decision-surface strong-watch-surface">\n'
        '<header class="codex-page-header">\n'
        '<span class="codex-status-chip" data-state="normal">STRONG WATCH / ENTRY REVIEW</span>\n'
        f'<h1>{html.escape(summary.title)}</h1>\n'
        '<p>AI/Data Center需要が受注・能力増強・売上・利益へどこまで転換したかを3社で比較します。</p>\n'
        '<div class="codex-page-header__meta">'
        f'<span class="codex-status-chip" data-state="{freshness_state}">Freshness: {freshness}</span>'
        '<span class="codex-status-chip" data-state="unavailable">Valuation: 3社とも未接続 / UNKNOWN</span>'
        f'<span>Source: {html.escape(summary.source_name)}</span>'
        '</div>\n'
        '</header>\n'
        '<div class="codex-summary-grid strong-watch-grid">\n'
        + "\n".join(cards)
        + '\n</div>\n'
        '<div class="codex-action-row">'
        '<a class="codex-action codex-action--primary" href="#watch-details">各社のTrigger / Risk / Checkpointを見る</a>'
        '<a class="codex-action codex-action--secondary" href="{{ \'/companies/\' | relative_url }}">Companies一覧へ</a>'
        '</div>\n'
        '</section>\n'
    )


def render_company_page_summary(summary: CompanyCardSummary) -> str:
    if _is_strong_watch_summary(summary):
        return _render_strong_watch_summary(summary)

    freshness = html.escape(summary.freshness) if summary.freshness else "更新日未記録"
    freshness_state = "normal" if summary.freshness else "unavailable"
    section_count = len(summary.sections)
    section_preview = " / ".join(html.escape(item) for item in summary.sections[:4])
    if not section_preview:
        section_preview = "構造化セクション未記録"

    return (
        '<section class="codex-page-shell company-decision-surface">\n'
        '<header class="codex-page-header">\n'
        f'<span class="codex-status-chip" data-state="normal">{html.escape(summary.category)}</span>\n'
        f'<h1>{html.escape(summary.title)}</h1>\n'
        '<div class="codex-page-header__meta">'
        f'<span class="codex-status-chip" data-state="{freshness_state}">Freshness: {freshness}</span>'
        f'<span>Source: {html.escape(summary.source_name)}</span>'
        '</div>\n'
        '</header>\n'
        '<div class="codex-summary-grid">\n'
        '<article class="codex-summary-card">'
        '<span class="codex-card-question">30秒で何を確認できる？</span>'
        f'<h2>{section_count} sections</h2>'
        f'<p>{section_preview}</p>'
        '</article>\n'
        '<article class="codex-summary-card">'
        '<span class="codex-card-question">Canonical metrics</span>'
        '<span class="codex-status-chip" data-state="unavailable">未接続値はUNAVAILABLE</span>'
        '<h2>推測しない</h2>'
        '<p>AI Score / KPI / PER / 需給はCanonical sourceに存在する値だけを利用します。</p>'
        '</article>\n'
        '</div>\n'
        '<div class="codex-action-row">'
        '<a class="codex-action codex-action--primary" href="#company-detail">詳細研究を見る</a>'
        '<a class="codex-action codex-action--secondary" href="{{ \'/companies/\' | relative_url }}">Companies一覧へ</a>'
        '</div>\n'
        '</section>\n'
    )


def canonical_detail_body(content: str) -> str:
    """Keep canonical research intact except for the duplicate document H1 in the disclosure."""
    return TITLE.sub("", content, count=1).lstrip()


def _strong_watch_mobile_detail(content: str) -> str:
    body = canonical_detail_body(content)
    body = re.sub(
        r"^##\s+3社比較\s*$.*?(?=^##\s+Valuation / Scenario\s*$)",
        "",
        body,
        flags=re.MULTILINE | re.DOTALL,
    )
    body = re.sub(
        r"^##\s+Valuation / Scenario\s*$.*?(?=^##\s+5805 SWCC\s*$)",
        (
            "## Valuation / Scenario\n\n"
            '<div class="codex-alert" data-state="unavailable">'
            '<strong>3社ともValuation未接続 / UNKNOWN</strong><br>'
            'Bear / Base / Bull EPS、fresh-price Forward PER、EPS +10% sensitivityは'
            'canonical basisが揃うまで推定しません。'
            '</div>\n\n'
        ),
        body,
        flags=re.MULTILINE | re.DOTALL,
    )
    body = body.replace("## 5805 SWCC", '<a id="watch-details"></a>\n<a id="watch-5805"></a>\n\n## 5805 SWCC', 1)
    body = body.replace("## 6504 富士電機", '<a id="watch-6504"></a>\n\n## 6504 富士電機', 1)
    body = body.replace("## 6622 ダイヘン", '<a id="watch-6622"></a>\n\n## 6622 ダイヘン', 1)
    return body.strip()


def render_company_detail(content: str) -> str:
    if _is_strong_watch_content(content):
        return (
            '<section class="codex-page-shell strong-watch-detail">\n'
            '<div class="codex-disclosure__body" markdown="1">\n\n'
            + _strong_watch_mobile_detail(content)
            + '\n\n</div>\n</section>\n'
        )

    return (
        '<section class="codex-page-shell">\n'
        '<details class="codex-disclosure" id="company-detail">\n'
        '<summary>Company Research 詳細</summary>\n'
        '<div class="codex-disclosure__body" markdown="1">\n\n'
        + canonical_detail_body(content).strip()
        + '\n\n</div>\n</details>\n</section>\n'
    )


def render_company_index_card(title: str, category: str, url: str, source_name: str) -> str:
    return (
        f'<a class="codex-summary-card" href="{{{{ \'{url}\' | relative_url }}}}">'
        f'<span class="codex-card-question">{html.escape(category)}</span>'
        f'<h3>{html.escape(title)}</h3>'
        f'<span>{html.escape(source_name)}</span>'
        '</a>'
    )
