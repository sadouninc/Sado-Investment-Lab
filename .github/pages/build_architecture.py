from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / ".github" / "pages"
SOURCE = ROOT / "06_Research" / "Architecture"
SITE_ROOT = ROOT / "site-src"
SITE = SITE_ROOT / "architecture"
DESIGN_SYSTEM_CSS = PAGES / "design-system.css"


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
    destination = SITE_ROOT / "assets" / "design-system.css"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DESIGN_SYSTEM_CSS, destination)


def main() -> None:
    publish_shared_assets()
    sources = sorted(
        path for path in SOURCE.glob("*.md")
        if path.name.lower() != "readme.md"
    )
    cards: list[str] = []

    for source in sources:
        page_slug = slug(source.stem)
        title = title_from_markdown(source)
        url = f"/architecture/{page_slug}/"
        cards.append(
            f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
            f"<strong>{title}</strong><span>{source.name}</span></a>"
        )

        page = front_matter(
            title,
            f"{title} — Sado Investment Lab のシステム設計",
            url,
        )
        page += (
            '<p class="breadcrumb"><a href="{{ \'/architecture/\' | relative_url }}">'
            f"Architecture</a> / {title}</p>\n\n"
        )
        page += source.read_text(encoding="utf-8")
        write(SITE / page_slug / "index.md", page)

    index = front_matter(
        "Architecture",
        "Investment Decision OS と分析基盤の設計ドキュメント",
        "/architecture/",
    )
    index += (
        "# Architecture\n\n"
        "Sado Investment Lab を支える Investment Decision OS、データモデル、"
        "分析エンジンの設計をまとめます。\n\n"
    )
    if cards:
        index += '<div class="content-grid">\n' + "\n".join(cards) + "\n</div>\n"
    else:
        index += "公開中の設計ドキュメントはありません。\n"
    write(SITE / "index.md", index)


if __name__ == "__main__":
    main()
