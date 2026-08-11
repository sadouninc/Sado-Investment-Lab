from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path


UPDATED = re.compile(r"^Updated:\s*(.+?)\s*$", re.MULTILINE)
HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TITLE = re.compile(r"^#\s+.+?\s*$", re.MULTILINE)


@dataclass(frozen=True)
class CompanyCardSummary:
    title: str
    category: str
    source_name: str
    freshness: str | None
    sections: tuple[str, ...]


def summarize_company(title: str, category: str, source: Path, content: str) -> CompanyCardSummary:
    updated = UPDATED.search(content)
    sections = tuple(dict.fromkeys(match.group(1).strip() for match in HEADING.finditer(content)))
    return CompanyCardSummary(
        title=title,
        category=category,
        source_name=source.name,
        freshness=updated.group(1).strip() if updated else None,
        sections=sections,
    )


def render_company_page_summary(summary: CompanyCardSummary) -> str:
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


def render_company_detail(content: str) -> str:
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
