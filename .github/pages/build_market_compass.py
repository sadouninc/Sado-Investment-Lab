"""Build Market Compass v0.1 page for owner-facing portfolio risk management."""
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO_PATH = ROOT / "data" / "portfolio" / "current.json"
REENTRY_WATCH_PATH = ROOT / "06_Research" / "market_compass" / "w33_reentry_watch_v0_1.json"


@dataclass(frozen=True)
class PortfolioPosition:
    """Current portfolio position with authority metadata."""
    security_code: str
    security_name: str
    position_type: str
    quantity: int
    authority_status: str  # VERIFIED, PROVISIONAL, MISMATCH, STALE
    as_of: str


@dataclass(frozen=True)
class ReentryCandidate:
    """Re-entry watch candidate from confirmed exits."""
    security_code: str
    name: str
    exit_date: str
    exit_price: float
    exit_quantity: int
    exit_type: str
    benchmark: str
    initial_state: str
    fundamental_integrity: str
    fundamental_strength_score: float | None
    valuation_reset_score: float | None
    excess_decline_score: float | None
    risk_stabilization_score: float | None
    confidence: str
    notes: str


@dataclass(frozen=True)
class MarketCompassState:
    """Market Compass state for a security."""
    security_code: str
    security_name: str
    compass_state: str  # AVOID, WATCH, BUY_WATCH, RE_ENTRY_READY
    fundamental_integrity: str  # PASS, REVIEW, FAIL, UNKNOWN
    excess_decline_score: float | None
    valuation_reset_score: float | None
    fundamental_strength_score: float | None
    risk_stabilization_score: float | None
    total_score: float | None
    confidence: str  # HIGH, MEDIUM, LOW
    evidence_timestamp: str
    source_refs: str


def load_portfolio() -> tuple[list[PortfolioPosition], dict[str, Any]]:
    """Load current portfolio with authority metadata."""
    if not PORTFOLIO_PATH.exists():
        return [], {"status": "FILE_MISSING", "as_of": "UNKNOWN"}
    
    data = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    
    authority = {
        "status": data.get("verification_status", "UNKNOWN"),
        "as_of": data.get("as_of", "UNKNOWN"),
        "base_snapshot": data.get("base_snapshot", "UNKNOWN"),
        "verification_source": data.get("verification_source", "UNKNOWN"),
    }
    
    positions = [
        PortfolioPosition(
            security_code=pos["security_code"],
            security_name=pos["security_name"],
            position_type=pos["position_type"],
            quantity=pos["quantity"],
            authority_status=authority["status"],
            as_of=authority["as_of"],
        )
        for pos in data.get("positions", [])
    ]
    
    return positions, authority


def load_reentry_watch() -> tuple[list[ReentryCandidate], dict[str, Any]]:
    """Load re-entry watch candidates from W33 v0.1."""
    if not REENTRY_WATCH_PATH.exists():
        return [], {"status": "FILE_MISSING", "as_of": "UNKNOWN", "macro_state": "UNKNOWN"}
    
    data = json.loads(REENTRY_WATCH_PATH.read_text(encoding="utf-8"))
    
    metadata = {
        "as_of": data.get("as_of", "UNKNOWN"),
        "event": data.get("event", "UNKNOWN"),
        "macro_state": data.get("macro_state", "UNKNOWN"),
        "mode": data.get("mode", "UNKNOWN"),
        "threshold_contract": data.get("threshold_contract", "UNKNOWN"),
    }
    
    candidates = []
    for cand in data.get("candidates", []):
        candidates.append(
            ReentryCandidate(
                security_code=cand["security_code"],
                name=cand["name"],
                exit_date=cand["exit_date"],
                exit_price=cand["exit_price"],
                exit_quantity=cand["exit_quantity"],
                exit_type=cand["exit_type"],
                benchmark=cand["benchmark"],
                initial_state=cand["initial_state"],
                fundamental_integrity=cand["fundamental_integrity"],
                fundamental_strength_score=cand.get("fundamental_strength_score"),
                valuation_reset_score=cand.get("valuation_reset_score"),
                excess_decline_score=cand.get("excess_decline_score"),
                risk_stabilization_score=cand.get("risk_stabilization_score"),
                confidence="MEDIUM",  # Default for v0.1
                notes=cand.get("notes", ""),
            )
        )
    
    return candidates, metadata


def compute_compass_state(
    fundamental_integrity: str,
    excess_decline: float | None,
    valuation_reset: float | None,
    fundamental_strength: float | None,
    risk_stabilization: float | None,
    confidence: str,
) -> str:
    """
    Compute Market Compass state per #568 v0.1.
    
    State Machine:
    - AVOID: Fundamental Integrity FAIL/UNKNOWN or deterioration not quantified
    - WATCH: Integrity PASS/REVIEW, total < 50 OR Risk Stabilization < 10
    - BUY WATCH: Integrity PASS, total >= 50, Excess Decline >= 10, 
                 Fundamental Strength >= 10, Risk Stabilization >= 5
    - RE_ENTRY_READY: Integrity PASS, total >= 70, Excess Decline >= 10,
                      Fundamental Strength >= 10, Risk Stabilization >= 15,
                      confidence not LOW
    """
    # AVOID: Fundamental Integrity FAIL or UNKNOWN
    if fundamental_integrity in ("FAIL", "UNKNOWN"):
        return "AVOID"
    
    # Calculate total score (if all components available)
    scores = [excess_decline, valuation_reset, fundamental_strength, risk_stabilization]
    if any(s is None for s in scores):
        # Cannot compute total; default to WATCH for PASS/REVIEW integrity
        return "WATCH"
    
    total = sum(s for s in scores if s is not None)
    
    # Check RE_ENTRY_READY criteria
    if (
        fundamental_integrity == "PASS"
        and total >= 70
        and excess_decline >= 10
        and fundamental_strength >= 10
        and risk_stabilization >= 15
        and confidence != "LOW"
    ):
        return "RE_ENTRY_READY"
    
    # Check BUY_WATCH criteria
    if (
        fundamental_integrity == "PASS"
        and total >= 50
        and excess_decline >= 10
        and fundamental_strength >= 10
        and risk_stabilization >= 5
    ):
        return "BUY_WATCH"
    
    # Default to WATCH
    return "WATCH"


def render_boj_status(macro_state: str) -> str:
    """Render BOJ Early Warning status."""
    state_colors = {
        "GREEN": "supportive",
        "ORANGE": "challenging",
        "RED": "critical",
        "UNKNOWN": "unknown",
    }
    state_labels = {
        "GREEN": "BOJ re-entry observation inactive",
        "ORANGE": "BOJ shadow observation",
        "RED": "BOJ active observation",
        "UNKNOWN": "BOJ state unknown",
    }
    
    state = macro_state.upper()
    color = state_colors.get(state, "unknown")
    label = state_labels.get(state, state)
    
    return (
        f'<div class="codex-status-chip" data-state="{color}">{label}</div>\n'
        '<p class="codex-card-question">BOJ RED ≠ all stocks AVOID; '
        'RE_ENTRY_READY ≠ BOJ risk disappeared</p>\n'
    )


def render_current_holdings(positions: list[PortfolioPosition], authority: dict[str, Any]) -> str:
    """Render current holdings section."""
    if not positions:
        return '<div class="codex-alert" data-state="unavailable"><strong>現在の保有銘柄なし</strong></div>\n'
    
    # Show authority status prominently
    status = authority.get("status", "UNKNOWN")
    status_state = {
        "VERIFIED": "supportive",
        "PROVISIONAL": "challenging",
        "MISMATCH": "critical",
        "STALE": "stale",
    }.get(status, "unknown")
    
    html_parts = [
        f'<div class="codex-alert" data-state="{status_state}">',
        f'<strong>Portfolio Authority: {html.escape(status)}</strong>',
        f'<p>As of: {html.escape(authority.get("as_of", "UNKNOWN"))} | ',
        f'Base: {html.escape(authority.get("base_snapshot", "UNKNOWN"))}</p>',
        '</div>\n',
        '<div class="codex-disclosure">',
        '<summary>Current Holdings (Provisional W33 Universe)</summary>',
        '<div class="codex-disclosure__body">',
        '<table style="width:100%; font-size: 0.85rem; margin-top: 1rem;">',
        '<thead><tr>',
        '<th style="text-align:left;">Code</th>',
        '<th style="text-align:left;">Name</th>',
        '<th style="text-align:left;">Type</th>',
        '<th style="text-align:right;">Qty</th>',
        '<th style="text-align:left;">Compass</th>',
        '</tr></thead><tbody>',
    ]
    
    for pos in positions:
        # For v0.1, we don't have compass state for all holdings yet
        # Show UNKNOWN as placeholder
        compass_state = "UNKNOWN"
        html_parts.extend([
            '<tr>',
            f'<td>{html.escape(pos.security_code)}</td>',
            f'<td>{html.escape(pos.security_name)}</td>',
            f'<td style="font-size:0.75rem;">{html.escape(pos.position_type)}</td>',
            f'<td style="text-align:right;">{pos.quantity}</td>',
            f'<td><span class="codex-status-chip" data-state="unknown">{compass_state}</span></td>',
            '</tr>',
        ])
    
    html_parts.extend([
        '</tbody></table>',
        '<p style="margin-top: 1rem; font-size: 0.8rem; color: var(--codex-text-muted);">',
        'Market Compass state requires sensor integration (Issue #568). UNKNOWN ≠ neutral.</p>',
        '</div></div>\n',
    ])
    
    return "".join(html_parts)


def render_reentry_watch(candidates: list[ReentryCandidate]) -> str:
    """Render re-entry watch section."""
    if not candidates:
        return '<div class="codex-alert"><strong>Re-entry Watch: No confirmed exits</strong></div>\n'
    
    html_parts = [
        '<h2 style="margin-top: 2rem;">Re-entry Watch</h2>\n',
        '<p>Confirmed exits from W33 under BOJ RED observation. ',
        'Not buy recommendations — read-only re-evaluation candidates.</p>\n',
        '<div class="codex-summary-grid" style="grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));">',
    ]
    
    for cand in candidates:
        compass_state = compute_compass_state(
            cand.fundamental_integrity,
            cand.excess_decline_score,
            cand.valuation_reset_score,
            cand.fundamental_strength_score,
            cand.risk_stabilization_score,
            cand.confidence,
        )
        
        state_colors = {
            "AVOID": "critical",
            "WATCH": "challenging",
            "BUY_WATCH": "normal",
            "RE_ENTRY_READY": "supportive",
        }
        
        html_parts.extend([
            '<div class="codex-summary-card">',
            f'<h3>{html.escape(cand.security_code)} {html.escape(cand.name)}</h3>',
            f'<div class="codex-status-chip" data-state="{state_colors.get(compass_state, "unknown")}">{compass_state}</div>',
            '<dl style="font-size: 0.82rem; margin-top: 0.75rem;">',
            f'<dt>Exit</dt><dd>{html.escape(cand.exit_date)} @ {cand.exit_price:,.0f}</dd>',
            f'<dt>Integrity</dt><dd>{html.escape(cand.fundamental_integrity)}</dd>',
            f'<dt>Benchmark</dt><dd>{html.escape(cand.benchmark)}</dd>',
            '</dl>',
            f'<p style="font-size: 0.75rem; color: var(--codex-text-muted); margin-top: 0.5rem;">{html.escape(cand.notes)}</p>',
            '</div>',
        ])
    
    html_parts.append('</div>\n')
    return "".join(html_parts)


def build_market_compass_page() -> str:
    """Build the complete Market Compass page."""
    positions, portfolio_auth = load_portfolio()
    candidates, reentry_meta = load_reentry_watch()
    
    page = (
        '---\n'
        'layout: site\n'
        'title: Market Compass\n'
        'description: Owner-facing risk management and re-entry observation\n'
        'permalink: /market-compass/\n'
        '---\n\n'
        '# Market Compass v0.1\n\n'
        '<p class="codex-card-question">現在保有の危険管理 + 売却済み優良株のRe-entry候補</p>\n\n'
    )
    
    # BOJ Early Warning status
    page += '<div class="codex-summary-card">\n<h2>Macro Risk Status</h2>\n'
    page += render_boj_status(reentry_meta.get("macro_state", "UNKNOWN"))
    page += f'<p style="font-size: 0.8rem; margin-top: 0.75rem;">Event: {html.escape(reentry_meta.get("event", "UNKNOWN"))}</p>\n'
    page += f'<p style="font-size: 0.8rem;">Mode: {html.escape(reentry_meta.get("mode", "UNKNOWN"))}</p>\n'
    page += '</div>\n\n'
    
    # Current Holdings
    page += '<h2>Current Holdings</h2>\n'
    page += render_current_holdings(positions, portfolio_auth)
    
    # Re-entry Watch
    page += render_reentry_watch(candidates)
    
    # Data Quality footer
    page += (
        '\n## Data Quality\n\n'
        '- State contract: Issue #568 v0.1 (frozen until first BOJ event ends)\n'
        '- BOJ precursor: Issue #512\n'
        '- UNKNOWN ≠ zero; UNKNOWN propagates fail-closed\n'
        '- No automatic buy/sell/hold recommendations\n'
        '- No order placement or broker mutation\n'
        f'- Re-entry watch as of: {html.escape(reentry_meta.get("as_of", "UNKNOWN"))}\n'
    )
    
    return page
