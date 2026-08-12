from __future__ import annotations

import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
REPORT_DIR = ROOT / "05_Daily_Reports" / "Morning"
DIAG_DIR = ROOT / "data" / "generated" / "diagnostics" / "openai"


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


def strip_source_front_matter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            return text[end + 5 :].lstrip()
    return text


def report_date(path: Path) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
        return path.stem
    return path.stem


def section_content(text: str, *headings: str) -> str:
    """Return a level-2 report section without performing AI re-summarization."""
    body = strip_source_front_matter(text)
    sections = list(re.finditer(r"^##\s+(.+?)\s*$", body, re.MULTILINE))
    for index, match in enumerate(sections):
        if match.group(1).strip() not in headings:
            continue
        end = sections[index + 1].start() if index + 1 < len(sections) else len(body)
        return body[match.end() : end].strip()
    return ""


def compact_summary(text: str, *, limit: int = 110) -> str:
    """Extract the first meaningful human-readable statement deterministically."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("###"):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"
    return ""


def report_card_summary(text: str) -> dict[str, str]:
    """Build navigation metadata only from stable report sections."""
    market = compact_summary(section_content(text, "市場概況", "Market"))
    strategy = compact_summary(section_content(text, "今日の戦略", "Today Strategy"))
    watch = compact_summary(section_content(text, "注目銘柄", "Key Watch", "Watchlist"))
    risk = compact_summary(section_content(text, "リスク要因", "Risk Factors"))
    return {
        "market": market,
        "strategy": strategy,
        "watch": watch,
        "risk": risk,
    }


def card_detail(summary: dict[str, str], status: object) -> str:
    rows: list[str] = []
    if summary.get("market"):
        rows.append(f"市場: {summary['market']}")
    if summary.get("strategy"):
        rows.append(f"戦略: {summary['strategy']}")
    if summary.get("watch"):
        rows.append(f"注目: {summary['watch']}")
    elif summary.get("risk"):
        rows.append(f"リスク: {summary['risk']}")
    rows = rows[:3]
    rows.append(f"Data quality: {status or 'unknown'}")
    return "<br>".join(html.escape(row) for row in rows)


def latest_report_card(day: str, url: str, summary: dict[str, str], status: object) -> str:
    """Render the latest decision-oriented report before any implementation explanation."""
    return (
        '<section aria-labelledby="morning-latest">\n'
        '<h2 id="morning-latest">今日まず見る</h2>\n'
        f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
        f'<strong>最新レポート {html.escape(day)}</strong>'
        f'<span>{card_detail(summary, status)}</span></a>\n'
        '</section>\n'
    )


def build() -> None:
    sources = sorted(REPORT_DIR.glob("*.md"), reverse=True) if REPORT_DIR.exists() else []
    cards: list[str] = []
    latest: tuple[str, str, dict[str, str], object] | None = None
    for source in sources:
        day = report_date(source)
        url = f"/reports/morning/{day}/"
        diagnostics_path = DIAG_DIR / f"{day}.json"
        diagnostics = {}
        if diagnostics_path.exists():
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
        model = diagnostics.get("model", "unknown")
        tokens = diagnostics.get("total_tokens")
        status = diagnostics.get("dataset_status", "unknown")
        report_text = source.read_text(encoding="utf-8")
        summary = report_card_summary(report_text)
        if latest is None:
            latest = (day, url, summary, status)
        else:
            cards.append(
                f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
                f"<strong>{day}</strong><span>{card_detail(summary, status)}</span></a>"
            )
        page = front_matter(
            f"朝の市場レポート {day}",
            "Morning Datasetを分析した朝の市場・投資チェック",
            url,
        )
        page += (
            '<p class="breadcrumb"><a href="{{ \'/reports/morning/\' | relative_url }}">'
            f"朝の市場レポート</a> / {day}</p>\n\n"
        )
        page += strip_source_front_matter(report_text)
        if diagnostics:
            page += (
                "\n\n## API Diagnostics\n\n"
                f"- Model: `{model}`\n"
                f"- Dataset status: `{status}`\n"
                f"- Input tokens: `{diagnostics.get('input_tokens')}`\n"
                f"- Output tokens: `{diagnostics.get('output_tokens')}`\n"
                f"- Total tokens: `{tokens}`\n"
                f"- Execution: `{diagnostics.get('execution_seconds')} sec`\n"
                f"- Estimated cost USD: `{diagnostics.get('estimated_cost_usd')}` "
                f"({diagnostics.get('cost_basis')})\n"
            )
        write(SITE / "reports" / "morning" / day / "index.md", page)

    index = front_matter(
        "朝の市場レポート",
        "最新日の市場要点・戦略・注目銘柄から確認できる朝の投資チェック",
        "/reports/morning/",
    )
    index += "# 朝の市場レポート\n\n"
    if latest:
        index += latest_report_card(*latest) + "\n"
        if cards:
            index += "## 過去のレポート\n\n<div class=\"content-grid\">\n" + "\n".join(cards) + "\n</div>\n\n"
        index += (
            "<details class=\"codex-disclosure\">\n"
            "<summary>このレポートについて</summary>\n"
            "<div class=\"codex-disclosure__body\" markdown=\"1\">\n\n"
            "Morning Datasetを基に生成した朝レポートの履歴です（旧称: AI Morning Reports）。"
            "一覧では市場概況・今日の戦略・注目銘柄を先に確認できます。\n\n"
            "生成処理のmodel / token / execution / costは個別レポート末尾のAPI Diagnosticsで確認できます。"
            "AIの出力は判断材料であり、事実データと推論を分離して扱います。\n\n"
            "</div>\n</details>\n"
        )
    else:
        index += "まだ朝の市場レポートは生成されていません。\n"
    write(SITE / "reports" / "morning" / "index.md", index)


if __name__ == "__main__":
    build()
