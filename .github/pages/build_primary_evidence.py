from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
REGISTRY = ROOT / "data" / "evidence" / "primary-evidence-archive.json"
RESEARCH_ROOT = ROOT / "data" / "research" / "company"


def front_matter(title: str, description: str, permalink: str) -> str:
    return (
        "---\n"
        "layout: site\n"
        f"title: {title}\n"
        f"description: {description}\n"
        f"permalink: {permalink}\n"
        "---\n\n"
    )


def load_registry() -> list[dict[str, Any]]:
    if not REGISTRY.is_file():
        return []
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("records"), list):
        raise ValueError("primary evidence registry must use schema_version=1 with records array")
    return [dict(record) for record in payload["records"]]


def discover_company_sources() -> dict[str, dict[str, Any]]:
    companies: dict[str, dict[str, Any]] = {}
    if not RESEARCH_ROOT.is_dir():
        return companies
    for path in sorted(RESEARCH_ROOT.glob("*/company-research-v1.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        code = str(raw.get("security_code") or path.parent.name)
        refs = [str(ref) for ref in raw.get("source_refs", []) if str(ref).strip()]
        companies[code] = {
            "security_code": code,
            "company_name": str(raw.get("company_name") or code),
            "source_refs": refs,
            "research_as_of": raw.get("as_of"),
        }
    return companies


def source_rows(records: list[Mapping[str, Any]], companies: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_original_url = {
        str(record.get("original_url")): record
        for record in records
        if record.get("original_url")
    }
    rows: list[dict[str, Any]] = []
    for code, company in companies.items():
        for ref in company.get("source_refs", []):
            archive = by_original_url.get(str(ref))
            rows.append({
                "security_code": code,
                "company_name": company.get("company_name") or code,
                "research_as_of": company.get("research_as_of"),
                "source_ref": str(ref),
                "source_id": archive.get("source_id") if archive else None,
                "access_status": archive.get("access_status") if archive else "URL_ONLY",
                "archive_ref": archive.get("archive_ref") if archive else None,
                "original_filename": archive.get("original_filename") if archive else None,
                "sha256": archive.get("sha256") if archive else None,
            })
    return sorted(rows, key=lambda row: (row["security_code"], row["source_ref"]))


def render_library(rows: list[Mapping[str, Any]]) -> str:
    page = front_matter(
        "Primary Evidence Library",
        "決算・IR一次資料の保存状態とResearchからの参照関係を確認する",
        "/sources/",
    )
    page += "# Primary Evidence Library\n\n"
    page += (
        "Company Researchで参照している一次資料を一覧化します。"
        "`ARCHIVED` はLabから再取得可能、`URL_ONLY` は公式URLのみ確認済みです。\n\n"
        '<p class="breadcrumb"><a href="{{ \'/companies/\' | relative_url }}">Companies</a> / Sources</p>\n\n'
    )
    if not rows:
        page += "> まだCompany Researchに紐づく一次資料はありません。\n"
        return page

    page += "| Company | Research as of | Status | Source | Archived copy | Integrity |\n"
    page += "|---|---|---|---|---|---|\n"
    for row in rows:
        source = f"[official]({row['source_ref']})"
        archive = f"[open]({row['archive_ref']})" if row.get("archive_ref") else "—"
        digest = str(row.get("sha256") or "—")
        if digest != "—":
            digest = f"`{digest[:12]}…`"
        page += (
            f"| {row['security_code']} {row['company_name']} | {row.get('research_as_of') or '—'} "
            f"| `{row.get('access_status') or 'URL_ONLY'}` | {source} | {archive} | {digest} |\n"
        )
    return page


def append_company_source_link() -> None:
    path = SITE / "companies" / "index.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    marker = "## Primary Evidence\n"
    if marker in text:
        return
    text = text.rstrip() + (
        "\n\n## Primary Evidence\n\n"
        '<a class="content-card" href="{{ \'/sources/\' | relative_url }}">'
        "<strong>決算・IR一次資料</strong><span>保存状態・公式URL・Archived copyを確認</span></a>\n"
    )
    path.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    rows = source_rows(load_registry(), discover_company_sources())
    target = SITE / "sources" / "index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_library(rows).rstrip() + "\n", encoding="utf-8")
    append_company_source_link()


if __name__ == "__main__":
    main()
