"""Read-only Development Diary renderer core for Issue #737."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import jsonschema

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data/contracts/development-diary-daily-v1.schema.json"
UNKNOWN_LABEL = "不明 / 未取得"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    validator = jsonschema.Draft202012Validator(load_schema(), format_checker=jsonschema.FormatChecker())
    validator.validate(snapshot)


def display_value(value: Any) -> str:
    if value is None:
        return UNKNOWN_LABEL
    if isinstance(value, bool):
        return "はい" if value else "いいえ"
    return html.escape(str(value))


def evidence_ref(ref: str) -> str:
    escaped = html.escape(ref)
    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f'<a href="{escaped}" rel="noopener noreferrer">{escaped}</a>'
    return f"<code>{escaped}</code>"


def evidence_refs(refs: Iterable[str]) -> str:
    items = "".join(f"<li>{evidence_ref(ref)}</li>" for ref in refs)
    return f'<ul class="evidence-list">{items}</ul>' if items else '<span class="unknown">不明 / 未取得</span>'


def metric_cards(values: dict[str, Any], labels: dict[str, str]) -> str:
    cards = []
    for key, label in labels.items():
        cards.append(
            '<div class="metric-card">'
            f'<dt>{html.escape(label)}</dt><dd data-field="{html.escape(key)}">{display_value(values.get(key))}</dd>'
            "</div>"
        )
    return '<dl class="metric-grid">' + "".join(cards) + "</dl>"


def render_snapshot(snapshot: dict[str, Any]) -> str:
    """Validate schema v1 first, then render one Japanese-first accessible HTML page."""
    validate_snapshot(snapshot)

    factory = metric_cards(snapshot["factory_output"], {
        "ready_count": "READY件数", "implementation_start_count": "実装開始件数",
        "pr_opened": "PR作成", "pr_merged": "PRマージ", "pr_closed_unmerged": "未マージClose",
        "durable_output_count": "Durable Output", "productive_step_count": "Productive Step",
        "lead_time_minutes": "リードタイム（分）",
    })

    flow = metric_cards(snapshot["flow_health"], {
        "active_implementation_wip": "Active Implementation WIP", "waiting_work_count": "待機work",
        "ready_nonconflicting_count": "非競合READY", "queue_replenish_latency_minutes": "Queue補充遅延（分）",
        "path_owner_conflict_count": "Path競合", "ci_stall_count": "CI停滞",
        "starvation_state": "Starvation状態", "blocked_escape_count": "BLOCKED_ESCAPE",
        "human_intervention_count": "Human intervention", "durable_output_interval_minutes": "Durable output間隔（分）",
    })

    economics = metric_cards(snapshot["economics"], {
        "free_executor_ratio": "Free executor比率", "paid_fallback_count": "Paid fallback",
        "copilot_usage_count": "Copilot使用回数", "copilot_credits": "Copilot credits",
        "ai_cost_per_accepted_unit": "Accepted unit当たりAI cost", "ai_cost_per_merge": "Merge当たりAI cost",
    })

    executor_rows = []
    for row in snapshot["executor_performance"]:
        metrics = metric_cards(row, {
            "dispatch_count": "DISPATCHED", "ack_count": "ACKED",
            "execution_evidence_count": "EXECUTION_EVIDENCE", "pr_count": "PR", "merge_count": "Merge",
            "success_count": "Success", "failure_count": "Failure", "terminal_noop_count": "Terminal noop",
            "elapsed_minutes": "Elapsed（分）", "lead_time_minutes": "Lead time（分）",
            "rework_count": "Rework", "duplicate_conflict_waste_count": "Duplicate/conflict waste",
        })
        executor_rows.append(
            '<article class="executor-card">'
            f'<h3>{html.escape(row["executor"])} <span class="task-class">{html.escape(row["task_class"])}</span></h3>'
            '<p class="semantic-note">DISPATCHED / ACKED は予約状態。実装開始は EXECUTION_EVIDENCE から。</p>'
            f"{metrics}</article>"
        )
    executors = "".join(executor_rows) or '<p class="unknown">不明 / 未取得</p>'

    capability_rows = []
    for change in snapshot["factory_capability_changes"]:
        status = change["validation_status"]
        capability_rows.append(
            '<article class="capability-card">'
            f'<h3>{html.escape(change["capability"])}</h3>'
            f'<p><span class="status status-{status.lower()}">{html.escape(status)}</span></p>'
            f'<p>有効日時: {display_value(change["effective_at"])}</p>'
            f'<p>Before: {display_value(change["before"])}</p><p>After: {display_value(change["after"])}</p>'
            f'<div><strong>Evidence</strong>{evidence_refs(change["evidence_refs"])}</div>'
            "</article>"
        )
    capabilities = "".join(capability_rows) or '<p>Factory Capability Changeなし</p>'

    correction_rows = []
    for correction in snapshot["corrections"]:
        correction_rows.append(
            '<article class="correction-card">'
            f'<h3>{html.escape(correction["correction_id"])}</h3>'
            f'<p>{html.escape(correction["reason"])}</p>'
            f'<p>記録日時: {display_value(correction["recorded_at"])}</p>'
            f'{evidence_refs(correction["evidence_refs"])}'
            "</article>"
        )
    corrections = "".join(correction_rows) or '<p>補正履歴なし</p>'

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Development Diary {html.escape(snapshot['diary_date_jst'])}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: system-ui, sans-serif; line-height: 1.6; color: #1f2937; background: #f8fafc; }}
main {{ width: min(100% - 24px, 1040px); margin: 0 auto; padding: 24px 0 48px; }}
section {{ margin-top: 24px; padding: 20px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap: 12px; margin: 0; }}
.metric-card {{ min-width: 0; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; overflow-wrap: anywhere; }}
dt {{ font-size: .9rem; color: #475569; }} dd {{ margin: 4px 0 0; font-weight: 700; }}
.executor-card,.capability-card,.correction-card {{ min-width: 0; margin-top: 12px; padding: 16px; border: 1px solid #e5e7eb; border-radius: 10px; overflow-wrap: anywhere; }}
.task-class,.status {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: .85rem; background: #eef2ff; }}
.status-pilot {{ border: 1px solid #b45309; }} .status-proven {{ border: 2px solid #166534; }} .status-unknown {{ border: 1px dashed #64748b; }}
.semantic-note,.unknown {{ color: #64748b; }} .evidence-list {{ padding-left: 1.2rem; overflow-wrap: anywhere; }}
@media (max-width: 390px) {{ main {{ width: min(100% - 16px, 100%); padding-top: 12px; }} section {{ padding: 14px; }} .metric-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<main>
<header><h1>Development Diary — {html.escape(snapshot['diary_date_jst'])}</h1><p>日次Factory snapshot。0は観測された0、不明値は「{UNKNOWN_LABEL}」として区別します。</p></header>
<section id="factory-output"><h2>Factory Output</h2>{factory}</section>
<section id="executor-performance"><h2>Executor Performance</h2>{executors}</section>
<section id="flow-health"><h2>Flow Health</h2>{flow}</section>
<section id="economics"><h2>Economics</h2>{economics}</section>
<section id="factory-capability-change"><h2>Factory Capability Change</h2>{capabilities}</section>
<section id="corrections"><h2>補正履歴</h2>{corrections}</section>
</main>
</body>
</html>
"""
