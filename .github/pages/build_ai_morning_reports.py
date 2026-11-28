from __future__ import annotations

from datetime import datetime, timedelta, timezone
import html
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site-src"
REPORT_DIR = ROOT / "05_Daily_Reports" / "Morning"
DIAG_DIR = ROOT / "data" / "generated" / "diagnostics" / "openai"
DEVELOPING_SIGNALS_BUILDER = Path(__file__).with_name("build_developing_signals.py")
JST = timezone(timedelta(hours=9))


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


def generated_at_label(value: object) -> str:
    """Format diagnostics generated_at for the owner-facing latest card in JST."""
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        return ""
    return parsed.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")


def dataset_status_label(status: object) -> str:
    """Keep internal status semantics while making the primary label Japanese-first."""
    normalized = str(status or "unknown").strip().upper()
    labels = {
        "OK": "データ状態: 取得済み",
        "COMPLETE": "データ状態: 取得済み",
        "PARTIAL": "データ状態: 一部取得できていません",
        "STALE": "データ状態: 情報が古いため再確認が必要",
        "UNAVAILABLE": "データ状態: 現在取得できません",
        "UNKNOWN": "データ状態: 確認できません",
    }
    return labels.get(normalized, f"データ状態: 確認が必要 ({normalized})")


UNVERIFIED_FOCUS_LABEL = "今日の検証済み注目銘柄は未確定"
VERIFIED_FOCUS_LABEL = "注目（候補データで検証済み）"
SECURITY_CODE_RE = re.compile(r"^[0-9][0-9A-Z][0-9][0-9A-Z]$")
_WATCH_HEADING_RE = re.compile(r"^##\s+(?:注目銘柄|Key Watch|Watchlist)\s*$", re.MULTILINE)
_MAX_NAME_CHARS = 60

VerifiedPair = tuple[str, str]


def verified_candidates(diagnostics: object, day: str) -> tuple[VerifiedPair, ...]:
    """Return canonical (security_code, company_name) pairs verified for this report day.

    The pairs come from the deterministic ``candidate_focus`` record written from
    canonical candidate rows, never from AI prose. Legacy diagnostics, malformed
    records, any malformed entry, or a record for another date fail closed.
    """
    if not isinstance(diagnostics, dict):
        return ()
    focus = diagnostics.get("candidate_focus")
    if not isinstance(focus, dict) or focus.get("verified_focus_available") is not True:
        return ()
    if focus.get("as_of") != day:
        return ()
    entries = focus.get("verified_candidates")
    if not isinstance(entries, list) or not entries:
        return ()
    pairs: list[VerifiedPair] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return ()
        code, name = entry.get("security_code"), entry.get("company_name")
        if not isinstance(code, str) or not SECURITY_CODE_RE.fullmatch(code):
            return ()
        if not isinstance(name, str) or not name.strip() or "\n" in name or len(name) > _MAX_NAME_CHARS:
            return ()
        pairs.append((code, name.strip()))
    return tuple(pairs)


def _pair_labels(pairs: tuple[VerifiedPair, ...]) -> str:
    return " / ".join(f"{code} {name}" for code, name in pairs)


def watch_line(summary: dict[str, str], *, pairs: tuple[VerifiedPair, ...] = ()) -> str:
    """Verified focus is rendered only from canonical pairs; AI prose stays an unverified memo."""
    if pairs:
        return f"{VERIFIED_FOCUS_LABEL}: {_pair_labels(pairs)}"
    watch = summary.get("watch") or ""
    return f"注目: {UNVERIFIED_FOCUS_LABEL}（AI候補メモ・未検証: {watch}）"


def watch_section_notice(diagnostics: object, pairs: tuple[VerifiedPair, ...]) -> str:
    memo = (
        "以下はAIが候補データから書いたメモで、銘柄ごとの照合はしていません。"
        "今日の推奨・新しい材料・現在の保有を示すものではありません。"
    )
    if pairs:
        labels = html.escape(_pair_labels(pairs))
        return f"> **{VERIFIED_FOCUS_LABEL}: {labels}**  \n> {memo}\n\n"
    focus = diagnostics.get("candidate_focus") if isinstance(diagnostics, dict) else None
    reason = focus.get("reason") if isinstance(focus, dict) else None
    detail = html.escape(str(reason)) if reason else "この日の候補が検証済みかどうかの記録がありません"
    return f"> **{UNVERIFIED_FOCUS_LABEL}。** {memo}（理由: {detail}）\n\n"


def annotate_watch_section(text: str, diagnostics: object, day: str) -> str:
    """Always label the AI watch section as an unverified memo (display only).

    The source report is not rewritten. When canonical verified pairs exist for
    this report day they are shown separately above the memo.
    """
    match = _WATCH_HEADING_RE.search(text)
    if not match:
        return text
    notice = watch_section_notice(diagnostics, verified_candidates(diagnostics, day))
    insert_at = match.end() + 1
    return text[:insert_at] + "\n" + notice + text[insert_at:].lstrip("\n")


def card_detail(
    summary: dict[str, str],
    status: object,
    *,
    generated_at: object = None,
    verified_pairs: tuple[VerifiedPair, ...] = (),
) -> str:
    """Preserve the established decision summary while adding freshness metadata."""
    rows: list[str] = []
    updated = generated_at_label(generated_at)
    if updated:
        rows.append(f"更新: {updated}")
    if summary.get("market"):
        rows.append(f"市場: {summary['market']}")
    if summary.get("strategy"):
        rows.append(f"戦略: {summary['strategy']}")
    if verified_pairs or summary.get("watch"):
        rows.append(watch_line(summary, pairs=verified_pairs))
    elif summary.get("risk"):
        rows.append(f"リスク: {summary['risk']}")
    rows.append(dataset_status_label(status))
    return "<br>".join(html.escape(row) for row in rows)


def latest_report_card(
    day: str,
    url: str,
    summary: dict[str, str],
    status: object,
    generated_at: object = None,
    verified_pairs: tuple[VerifiedPair, ...] = (),
) -> str:
    """Render the latest decision-oriented report before any implementation explanation."""
    return (
        '<section aria-labelledby="morning-latest">\n'
        '<h2 id="morning-latest">今日まず見る</h2>\n'
        f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
        f'<strong>最新レポート {html.escape(day)}</strong>'
        f'<span>{card_detail(summary, status, generated_at=generated_at, verified_pairs=verified_pairs)}</span></a>\n'
        '</section>\n'
    )


def build() -> None:
    sources = sorted(REPORT_DIR.glob("*.md"), reverse=True) if REPORT_DIR.exists() else []
    cards: list[str] = []
    latest: tuple[str, str, dict[str, str], object, object, tuple[VerifiedPair, ...]] | None = None
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
        generated_at = diagnostics.get("generated_at")
        report_text = source.read_text(encoding="utf-8")
        summary = report_card_summary(report_text)
        pairs = verified_candidates(diagnostics, day)
        if latest is None:
            latest = (day, url, summary, status, generated_at, pairs)
        else:
            cards.append(
                f'<a class="content-card" href="{{{{ \'{url}\' | relative_url }}}}">'
                f"<strong>{day}</strong><span>{card_detail(summary, status, verified_pairs=pairs)}</span></a>"
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
        page += annotate_watch_section(strip_source_front_matter(report_text), diagnostics, day)
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


def publish_developing_signals() -> None:
    """Publish the canonical Developing Signals read model in the existing post-build phase."""
    spec = importlib.util.spec_from_file_location("build_developing_signals", DEVELOPING_SIGNALS_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Developing Signals builder unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build()


if __name__ == "__main__":
    build()
    publish_developing_signals()
