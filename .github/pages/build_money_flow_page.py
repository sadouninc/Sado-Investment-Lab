from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from build_site import ROOT, SITE, front_matter, write

SECTOR_HISTORY_PATH = ROOT / "data" / "generated" / "public" / "money-flow" / "sector-history.jsonl"
INTRADAY_FLOW_PATH = ROOT / "data" / "generated" / "public" / "money-flow" / "intraday-subsector-flow.jsonl"
OUTPUT_PATH = SITE / "market" / "money-flow" / "index.md"

FLOW_STATE_ICONS = {
    "STRONG_INFLOW": "🔥",
    "INFLOW": "↗️",
    "MIXED": "↔️",
    "OUTFLOW": "↘️",
    "STRONG_OUTFLOW": "❄️",
    "UNKNOWN": "❓",
}

ACCELERATION_STATE_ICONS = {
    "ACCELERATING": "⚡",
    "DECELERATING": "🔽",
    "REVERSING": "🔄",
    "STABLE": "▬",
    "UNKNOWN": "—",
}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _format_pct(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{float(value) * 100:+.1f}%"


def _format_relative(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{float(value) * 100:+.1f}pt"


def _format_breadth(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{float(value) * 100:.0f}%"


def _format_ratio(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{float(value):.1f}x"


def _load_latest_sector_snapshot() -> dict[str, Any] | None:
    """Load latest medium-term sector regime snapshot from sector-history.jsonl."""
    if not SECTOR_HISTORY_PATH.exists():
        return None
    lines = SECTOR_HISTORY_PATH.read_text(encoding="utf-8").strip().split("\n")
    if not lines or not lines[-1].strip():
        return None
    try:
        return json.loads(lines[-1])
    except (json.JSONDecodeError, ValueError):
        return None


def _load_intraday_flows() -> list[dict[str, Any]]:
    """Load intraday subsector flow snapshots from intraday-subsector-flow.jsonl."""
    if not INTRADAY_FLOW_PATH.exists():
        return []
    lines = INTRADAY_FLOW_PATH.read_text(encoding="utf-8").strip().split("\n")
    flows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            flows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return flows


def _render_medium_term_regime(snapshot: dict[str, Any] | None) -> str:
    """Render medium-term sector regime section (existing Money Flow detector output)."""
    html_parts: list[str] = []
    html_parts.append('<section aria-labelledby="medium-term-title">')
    html_parts.append('<p class="eyebrow">MEDIUM-TERM SECTOR REGIME</p>')
    html_parts.append('<h2 id="medium-term-title">Sector-level Trend (5d/20d/60d)</h2>')
    html_parts.append('<p class="lead">TOPIX-17 sector ETF proxy based. Daily timeframe. COLD/WARMING/HOT classification.</p>')

    if not isinstance(snapshot, Mapping):
        html_parts.append(
            '<div class="codex-alert" data-state="unavailable">'
            "<strong>Medium-term regime: UNAVAILABLE</strong>"
            "<p>Sector history snapshot not found. Medium-term regime data is missing.</p>"
            "</div>"
        )
        html_parts.append("</section>")
        return "\n".join(html_parts)

    observed_at = snapshot.get("observed_at", "unknown")
    sectors = snapshot.get("sectors", [])
    if not isinstance(sectors, list):
        sectors = []

    html_parts.append(f'<p><strong>Observed:</strong> {_escape(observed_at)}</p>')
    html_parts.append('<div class="codex-data-table-wrapper">')
    html_parts.append('<table class="codex-data-table">')
    html_parts.append("<thead><tr><th>Sector</th><th>Regime</th><th>Signal</th></tr></thead>")
    html_parts.append("<tbody>")

    for sector_data in sectors:
        if not isinstance(sector_data, Mapping):
            continue
        name = sector_data.get("name", "Unknown")
        signal = sector_data.get("signal", "UNKNOWN")
        explanation = sector_data.get("explanation", "")
        html_parts.append(
            f"<tr><td>{_escape(name)}</td><td>{_escape(signal)}</td><td>{_escape(explanation)}</td></tr>"
        )

    html_parts.append("</tbody></table></div>")
    html_parts.append(
        "<p><small>Source: Money Flow Detector (TOPIX-17 ETF proxy, daily bars, 5d/20d/60d relative return & activity)</small></p>"
    )
    html_parts.append("</section>")
    return "\n".join(html_parts)


def _render_intraday_flow_card(flow: dict[str, Any]) -> str:
    """Render a single intraday subsector flow card."""
    sector_label = flow.get("sector", {}).get("label", "Unknown Sector")
    medium_term_regime = flow.get("sector", {}).get("medium_term_regime", "UNKNOWN")
    subsector_label = flow.get("subsector", {}).get("label", "Unknown Subsector")
    observed_at = flow.get("observed_at", "unknown")
    freshness = flow.get("freshness", "UNKNOWN")
    completeness = flow.get("data_completeness", "UNKNOWN")
    flow_state = flow.get("flow_state", "UNKNOWN")
    acceleration_state = flow.get("acceleration_state", "UNKNOWN")
    obs = flow.get("observations", {})
    leaders = flow.get("leaders", [])

    flow_icon = FLOW_STATE_ICONS.get(flow_state, "")
    accel_icon = ACCELERATION_STATE_ICONS.get(acceleration_state, "")

    card_parts: list[str] = []
    card_parts.append('<article class="codex-money-flow-card">')
    card_parts.append(f'<h3>{_escape(subsector_label)}</h3>')
    card_parts.append(f'<p class="eyebrow">Parent Sector: {_escape(sector_label)}</p>')
    card_parts.append(f'<p><strong>Medium-term regime:</strong> {_escape(medium_term_regime)}</p>')
    card_parts.append("<hr>")
    card_parts.append(
        f'<p><strong>Intraday flow:</strong> {flow_icon} {_escape(flow_state)} {accel_icon} {_escape(acceleration_state)}</p>'
    )

    intraday_return = obs.get("intraday_return")
    relative_return = obs.get("relative_return")
    breadth = obs.get("breadth")
    turnover_ratio = obs.get("turnover_ratio")
    concentration = obs.get("concentration_top1")

    card_parts.append(f'<p><strong>Subsector return:</strong> {_format_pct(intraday_return)}</p>')
    card_parts.append(f'<p><strong>vs Benchmark:</strong> {_format_relative(relative_return)}</p>')
    card_parts.append(f'<p><strong>Breadth:</strong> {_format_breadth(breadth)}</p>')
    card_parts.append(f'<p><strong>Turnover ratio:</strong> {_format_ratio(turnover_ratio)}</p>')
    card_parts.append(f'<p><strong>Top-1 concentration:</strong> {_format_breadth(concentration)}</p>')

    if isinstance(leaders, list) and leaders:
        card_parts.append("<hr>")
        card_parts.append("<h4>Leaders</h4>")
        card_parts.append("<ul>")
        for leader in leaders[:5]:
            if not isinstance(leader, Mapping):
                continue
            code = leader.get("security_code", "")
            name = leader.get("name", "")
            ret = leader.get("intraday_return")
            card_parts.append(f"<li>{_escape(code)} {_escape(name)} {_format_pct(ret)}</li>")
        card_parts.append("</ul>")

    card_parts.append(
        f'<p class="codex-metadata"><small>Observed: {_escape(observed_at)}<br>Freshness: {_escape(freshness)} | Completeness: {_escape(completeness)}</small></p>'
    )
    card_parts.append("</article>")
    return "\n".join(card_parts)


def _render_intraday_flows(flows: list[dict[str, Any]]) -> str:
    """Render intraday subsector flow section with cards."""
    html_parts: list[str] = []
    html_parts.append('<section aria-labelledby="intraday-flow-title">')
    html_parts.append('<p class="eyebrow">INTRADAY SUBSECTOR / THEME FLOW</p>')
    html_parts.append('<h2 id="intraday-flow-title">Today\'s Localized Capital Flow</h2>')
    html_parts.append(
        '<p class="lead">Intraday observation. Subsector/Theme level. Early detection of capital inflow/outflow within sectors.</p>'
    )

    if not flows:
        html_parts.append(
            '<div class="codex-alert" data-state="unavailable">'
            "<strong>Intraday flow: UNAVAILABLE</strong>"
            "<p>No intraday subsector flow snapshots available. This is fail-closed: no data ≠ no flow.</p>"
            "</div>"
        )
        html_parts.append("</section>")
        return "\n".join(html_parts)

    # Group by sector to show hierarchy
    by_sector: dict[str, list[dict[str, Any]]] = {}
    for flow in flows:
        if not isinstance(flow, Mapping):
            continue
        sector_id = flow.get("sector", {}).get("id", "unknown")
        if sector_id not in by_sector:
            by_sector[sector_id] = []
        by_sector[sector_id].append(flow)

    # Render cards grouped by sector
    for sector_id, sector_flows in sorted(by_sector.items()):
        if not sector_flows:
            continue
        sector_label = sector_flows[0].get("sector", {}).get("label", sector_id)
        html_parts.append(f'<h3>{_escape(sector_label)}</h3>')
        html_parts.append('<div class="codex-money-flow-grid">')
        for flow in sector_flows:
            html_parts.append(_render_intraday_flow_card(flow))
        html_parts.append("</div>")

    html_parts.append(
        "<p><small>Source: Intraday Subsector Flow aggregation (constituent-level prices, intraday snapshot)</small></p>"
    )
    html_parts.append("</section>")
    return "\n".join(html_parts)


def _render_interpretation() -> str:
    """Render interpretation and usage guidance section."""
    html_parts: list[str] = []
    html_parts.append('<section aria-labelledby="interpretation-title">')
    html_parts.append('<p class="eyebrow">INTERPRETATION</p>')
    html_parts.append('<h2 id="interpretation-title">How to Read Two-Tier Money Flow</h2>')
    html_parts.append(
        '<div class="codex-alert" data-state="normal">'
        "<h3>Two Time Scales, Two Signals</h3>"
        "<p><strong>Medium-term Sector Regime (COLD/WARMING/HOT):</strong> Based on 5d/20d/60d relative return and activity. "
        "Describes sector-level trend persistence. Does NOT update intraday.</p>"
        "<p><strong>Intraday Subsector Flow (STRONG_INFLOW/INFLOW/MIXED/OUTFLOW/STRONG_OUTFLOW):</strong> Based on same-day "
        "relative return, breadth, concentration. Detects localized capital flows within a sector.</p>"
        "<p><strong>Example:</strong> Pharmaceutical sector = COLD (medium-term) while Biotechnology subsector = STRONG_INFLOW (today). "
        "This is NOT a contradiction. It means: sector trend is cold, but capital is entering a narrow subsector today.</p>"
        "</div>"
    )
    html_parts.append(
        '<div class="codex-alert" data-state="normal">'
        "<h3>Non-Directive Guardrail</h3>"
        "<p>Strong Theme Flow signal is NOT an automatic BUY/SELL command. It is an <strong>evidence signal</strong> for Decision Journal.</p>"
        "<p>When selling a holding that is a Subsector Leader during STRONG_INFLOW, consider:</p>"
        "<ul>"
        "<li>Is full exit necessary, or can Core Position be retained?</li>"
        "<li>What is the Thesis / valuation / risk / portfolio sizing trade-off?</li>"
        "<li>Flow signal does not override Thesis, but provides context for Decision Review.</li>"
        "</ul>"
        "<p>This signal prevents <em>\"I didn't know capital was flowing there\"</em> situations. "
        "The final decision remains with Owner + Thesis + Risk framework.</p>"
        "</div>"
    )
    html_parts.append("</section>")
    return "\n".join(html_parts)


def render_page(
    sector_snapshot: dict[str, Any] | None, intraday_flows: list[dict[str, Any]]
) -> str:
    """Render the complete Money Flow page with two-tier structure."""
    page = front_matter(
        "Money Flow",
        "二層Money Flow: Medium-term Sector Regime + Intraday Subsector Flow",
        "/market/money-flow/",
    )
    page += '<link rel="stylesheet" href="{{ \'/assets/design-system.css\' | relative_url }}">\n'
    page += '<style>.codex-money-flow-card { border: 1px solid var(--color-border, #ccc); padding: 1rem; margin-bottom: 1rem; border-radius: 4px; } .codex-money-flow-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 2rem; } .codex-metadata { color: var(--color-text-muted, #666); }</style>\n\n'
    page += '<div class="codex-page-shell">\n'
    page += '<header class="codex-page-header">'
    page += '<p class="eyebrow">MONEY FLOW</p>'
    page += '<h1>Market → Sector → Subsector → Stock</h1>'
    page += '<p class="lead">二層構造: Medium-term Sector RegimeとIntraday Subsector Flowを分離して表示します。'
    page += "Pharmaceutical=COLDかつBiotechnology=STRONG_INFLOWのような異なる時間軸の状態を同時に理解できます。</p>"
    page += "</header>\n"

    page += _render_medium_term_regime(sector_snapshot)
    page += _render_intraday_flows(intraday_flows)
    page += _render_interpretation()

    page += "</div>\n"
    return page


def main() -> None:
    sector_snapshot = _load_latest_sector_snapshot()
    intraday_flows = _load_intraday_flows()
    write(OUTPUT_PATH, render_page(sector_snapshot, intraday_flows))


if __name__ == "__main__":
    main()
