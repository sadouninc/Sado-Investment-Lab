from __future__ import annotations

import re
import shutil
from pathlib import Path

from build_primary_evidence import main as publish_primary_evidence_library
from company_cards import (
    render_company_detail,
    render_company_index_card,
    render_company_page_summary,
    summarize_company,
)


ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / ".github" / "pages"
SOURCE = ROOT / "06_Research" / "Architecture"
COMPANY_SOURCE = ROOT / "03_Companies"
SITE_ROOT = ROOT / "site-src"
SITE = SITE_ROOT / "architecture"
COMPANY_SITE = SITE_ROOT / "companies"
DESIGN_SYSTEM_CSS = PAGES / "design-system.css"
INSTRUMENT_SPRITE = PAGES / "instruments.svg"
NAVIGATION_SOURCE = PAGES / "navigation-v1.json"
SITE_LAYOUT = SITE_ROOT / "_layouts" / "site.html"

SITE_HEADER_RE = re.compile(r'  <header class="site-header">.*?  </header>\n', re.DOTALL)
GLOBAL_NAVIGATION_SHELL = r'''  <header class="codex-global-header">
    <div class="codex-global-header__brand-row">
      <a class="codex-global-brand" href="{{ '/' | relative_url }}">SADO INVESTMENT CODEX</a>
      <span class="codex-global-context" id="codex-global-context" aria-live="polite">現在地を確認中</span>
    </div>
    <nav class="codex-global-nav" aria-label="投資目的ナビゲーション">
      {% for item in site.data.navigation.navigation_groups %}
      <a class="codex-nav-item" data-nav-group="{{ item.id }}" href="{{ item.primary_destination | relative_url }}">
        <svg class="codex-instrument-icon codex-nav-item__icon" aria-hidden="true" viewBox="0 0 24 24"><use href="{{ '/assets/instruments.svg' | relative_url }}#{{ item.id }}"></use></svg>
        <span class="codex-nav-item__label">{{ item.label_ja }}</span>
      </a>
      {% endfor %}
    </nav>
  </header>
  <nav class="breadcrumb codex-global-breadcrumb" id="codex-global-breadcrumb" aria-label="現在地" hidden></nav>
  <script>
    (() => {
      const navigation = {{ site.data.navigation | jsonify }};
      const baseUrl = {{ site.baseurl | jsonify }} || '';
      let currentPath = window.location.pathname;
      if (baseUrl && currentPath.startsWith(baseUrl)) currentPath = currentPath.slice(baseUrl.length) || '/';
      if (!currentPath.startsWith('/')) currentPath = '/' + currentPath;
      if (!currentPath.endsWith('/')) currentPath += '/';

      const candidates = (navigation.routes || [])
        .filter((route) => route.availability === 'AVAILABLE' && route.route)
        .filter((route) => route.route === '/' ? currentPath === '/' : currentPath.startsWith(route.route))
        .sort((left, right) => right.route.length - left.route.length);
      const matchedRoute = candidates[0] || null;
      const currentGroup = matchedRoute?.primary_journey_stage || null;
      const group = (navigation.navigation_groups || []).find((item) => item.id === currentGroup);
      const context = document.getElementById('codex-global-context');
      if (context) context.textContent = group ? `現在地: ${group.label_ja}` : '現在地: 未分類';

      document.querySelectorAll('.codex-nav-item').forEach((item) => {
        const active = currentGroup && item.dataset.navGroup === currentGroup;
        item.toggleAttribute('data-current', Boolean(active));
        if (active) item.setAttribute('aria-current', 'location');
        else item.removeAttribute('aria-current');
      });

      const breadcrumb = document.getElementById('codex-global-breadcrumb');
      if (!breadcrumb || currentPath === '/') return;
      const pageTitle = document.querySelector('main.book-shell h1')?.textContent?.trim()
        || document.title.replace(/\s+[—-]\s+Sado Investment Lab$/, '').trim();
      const items = [{ label: 'Home', route: '/' }];
      if (group && group.id !== 'home') {
        items.push({ label: group.label_ja, route: group.primary_destination });
      } else if (!group) {
        items.push({ label: '未分類', route: null });
      }

      if (matchedRoute) {
        const routeSegments = Array.isArray(matchedRoute.breadcrumb_segments_ja)
          ? matchedRoute.breadcrumb_segments_ja
          : [matchedRoute.user_facing_label_ja];
        for (const label of routeSegments.filter(Boolean)) {
          if (items.some((item) => item.label === label)) continue;
          items.push({ label, route: matchedRoute.route });
        }
        if (currentPath !== matchedRoute.route && pageTitle && !items.some((item) => item.label === pageTitle)) {
          items.push({ label: pageTitle, route: null });
        }
      } else if (pageTitle) {
        items.push({ label: pageTitle, route: null });
      }

      const fragment = document.createDocumentFragment();
      items.forEach((item, index) => {
        if (index) fragment.append(' / ');
        const isLast = index === items.length - 1;
        if (item.route && !isLast) {
          const link = document.createElement('a');
          link.href = `${baseUrl}${item.route}`.replace(/\/+/g, '/');
          link.textContent = item.label;
          fragment.append(link);
        } else {
          const span = document.createElement('span');
          span.textContent = item.label;
          if (isLast) span.setAttribute('aria-current', 'page');
          fragment.append(span);
        }
      });
      breadcrumb.replaceChildren(fragment);
      breadcrumb.hidden = false;
    })();
  </script>
'''


def slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def title_from_markdown(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ")


def front_matter(title: str, description: str, permalink: str) -> str:
    return (
        "---\n"
        "layout: site\n"
        f"title: {title}\n"
        f"description: {description}\n"
        f"permalink: {permalink}\n"
        "---\n\n"
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def publish_shared_assets() -> None:
    if not DESIGN_SYSTEM_CSS.is_file():
        raise FileNotFoundError(f"missing shared design system asset: {DESIGN_SYSTEM_CSS}")
    if not INSTRUMENT_SPRITE.is_file():
        raise FileNotFoundError(f"missing Codex instrument sprite: {INSTRUMENT_SPRITE}")
    destination = SITE_ROOT / "assets" / "design-system.css"
    instrument_destination = SITE_ROOT / "assets" / "instruments.svg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DESIGN_SYSTEM_CSS, destination)
    shutil.copy2(INSTRUMENT_SPRITE, instrument_destination)


def publish_navigation_shell() -> None:
    if not NAVIGATION_SOURCE.is_file():
        raise FileNotFoundError(f"missing navigation contract: {NAVIGATION_SOURCE}")
    if not SITE_LAYOUT.is_file():
        raise FileNotFoundError(f"missing generated site layout: {SITE_LAYOUT}")

    data_dir = SITE_ROOT / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(NAVIGATION_SOURCE, data_dir / "navigation.json")

    layout = SITE_LAYOUT.read_text(encoding="utf-8")
    design_link = "  <link rel=\"stylesheet\" href=\"{{ '/assets/design-system.css' | relative_url }}\">\n"
    if design_link not in layout:
        book_link = "  <link rel=\"stylesheet\" href=\"{{ '/assets/book.css' | relative_url }}\">\n"
        if book_link not in layout:
            raise ValueError("site layout no longer contains the canonical book.css link")
        layout = layout.replace(book_link, book_link + design_link, 1)

    if "codex-global-header" not in layout:
        layout, replacements = SITE_HEADER_RE.subn(lambda _match: GLOBAL_NAVIGATION_SHELL, layout, count=1)
        if replacements != 1:
            raise ValueError("site layout no longer contains exactly one legacy site-header")

    SITE_LAYOUT.write_text(layout, encoding="utf-8")


def publish_company_cards() -> None:
    """Overwrite legacy long-form Company output with a summary-first read model.

    Canonical research files stay unchanged. Missing metrics remain unavailable instead of
    being inferred by the presentation layer.
    """
    sources = sorted(
        path
        for path in COMPANY_SOURCE.glob("*/*.md")
        if path.name.lower() != "readme.md"
    )
    groups: dict[str, list[str]] = {}
    for source in sources:
        category = source.parent.name
        category_slug = slug(category)
        page_slug = slug(source.stem)
        title = title_from_markdown(source)
        url = f"/companies/{category_slug}/{page_slug}/"
        content = source.read_text(encoding="utf-8")
        summary = summarize_company(title, category, source, content)
        groups.setdefault(category, []).append(
            render_company_index_card(title, category, url, source.name)
        )

        page = front_matter(title, f"{title}の企業分析", url)
        page += render_company_page_summary(summary)
        page += "\n"
        page += render_company_detail(content)
        write(COMPANY_SITE / category_slug / page_slug / "index.md", page)

    index = front_matter("Companies", "企業品質と投資機会を30秒で把握するCompany Cards", "/companies/")
    index += '<section class="codex-page-shell">\n'
    index += '<header class="codex-page-header"><h1>Companies</h1><p>企業ごとのCanonical Researchを、推測せずSummary-firstで確認します。</p></header>\n'
    for category, cards in groups.items():
        index += f"<h2>{category}</h2>\n"
        index += '<div class="codex-summary-grid">\n' + "\n".join(cards) + "\n</div>\n"
    if not groups:
        index += '<div class="codex-alert" data-state="unavailable"><strong>公開中の企業分析はありません。</strong></div>\n'
    index += "</section>\n"
    write(COMPANY_SITE / "index.md", index)


def main() -> None:
    publish_shared_assets()
    publish_navigation_shell()
    publish_company_cards()
    publish_primary_evidence_library()
    sources = sorted(path for path in SOURCE.glob("*.md") if path.name.lower() != "readme.md")
    cards: list[str] = []
    for source in sources:
        page_slug = slug(source.stem)
        title = title_from_markdown(source)
        url = f"/architecture/{page_slug}/"
        cards.append(f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}"><strong>{title}</strong><span>{source.name}</span></a>')
        page = front_matter(title, f"{title} — Sado Investment Lab のシステム設計", url)
        page += '<p class="breadcrumb"><a href="{{ \'/architecture/\' | relative_url }}">Architecture</a> / ' + title + '</p>\n\n'
        page += source.read_text(encoding="utf-8")
        write(SITE / page_slug / "index.md", page)

    index = front_matter("Architecture", "Investment Decision OS と分析基盤の設計ドキュメント", "/architecture/")
    index += "# Architecture\n\nSado Investment Lab を支える Investment Decision OS、データモデル、分析エンジンの設計をまとめます。\n\n"
    if cards:
        index += '<div class="content-grid">\n' + "\n".join(cards) + "\n</div>\n"
    else:
        index += "公開中の設計ドキュメントはありません。\n"
    write(SITE / "index.md", index)


if __name__ == "__main__":
    main()
