from __future__ import annotations

from typing import Any, Mapping, Sequence


VALID_RESULTS = {"PASS", "WARN", "BLOCK_REVIEW", "UNKNOWN"}
VALID_DATA_STATUS = {"CURRENT", "STALE", "PARTIAL", "UNKNOWN"}


class RiskPreflightIntegrationError(ValueError):
    pass


def _required_text(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RiskPreflightIntegrationError(f"{field} is required")
    return text


def _validate_snapshot(snapshot: Mapping[str, Any]) -> tuple[str, str, str, str]:
    snapshot_id = _required_text(snapshot.get("snapshot_id"), field="snapshot_id")
    captured_at = _required_text(snapshot.get("captured_at"), field="captured_at")
    proposed = snapshot.get("proposed_action")
    if not isinstance(proposed, Mapping):
        raise RiskPreflightIntegrationError("proposed_action is required")
    security_code = _required_text(proposed.get("security_code"), field="security_code")
    data_status = str(snapshot.get("data_status") or "UNKNOWN")
    if data_status not in VALID_DATA_STATUS:
        raise RiskPreflightIntegrationError("invalid data_status")
    guardrails = snapshot.get("guardrail_results")
    if not isinstance(guardrails, Sequence) or isinstance(guardrails, (str, bytes)):
        raise RiskPreflightIntegrationError("guardrail_results must be a sequence")
    for item in guardrails:
        if not isinstance(item, Mapping):
            raise RiskPreflightIntegrationError("guardrail result must be an object")
        result = str(item.get("result") or "")
        if result not in VALID_RESULTS:
            raise RiskPreflightIntegrationError("invalid guardrail result")
        _required_text(item.get("guardrail"), field="guardrail")
    return snapshot_id, captured_at, security_code, data_status


def decision_journal_ref(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return immutable reference metadata suitable for #133 system_snapshot."""
    snapshot_id, captured_at, security_code, data_status = _validate_snapshot(snapshot)
    return {
        "type": "RISK_PREFLIGHT_SNAPSHOT",
        "ref": snapshot_id,
        "captured_at": captured_at,
        "security_code": security_code,
        "data_status": data_status,
    }


def review_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Expose explicit review reasons without creating an owner BUY/SELL decision."""
    snapshot_id, captured_at, security_code, data_status = _validate_snapshot(snapshot)
    reasons: list[dict[str, str]] = []
    for item in snapshot["guardrail_results"]:
        result = str(item["result"])
        if result == "PASS":
            continue
        reasons.append(
            {
                "guardrail": str(item["guardrail"]),
                "result": result,
                "reason": str(item.get("reason") or "").strip() or "明示理由なし",
            }
        )
    if data_status != "CURRENT":
        reasons.append(
            {
                "guardrail": "PORTFOLIO_DATA_STATUS",
                "result": "UNKNOWN",
                "reason": f"portfolio data_status={data_status}",
            }
        )
    return {
        "type": "PORTFOLIO_RISK_PREFLIGHT_REVIEW_CONTEXT",
        "risk_snapshot_ref": snapshot_id,
        "captured_at": captured_at,
        "security_code": security_code,
        "reasons": reasons,
        "requires_owner_review": any(r["result"] == "BLOCK_REVIEW" for r in reasons),
        "trade_action": None,
    }


def feasible_capital_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return #186 context without claiming brokerage buying-power feasibility."""
    snapshot_id, captured_at, security_code, data_status = _validate_snapshot(snapshot)
    after = snapshot.get("after_if_executed")
    if not isinstance(after, Mapping):
        raise RiskPreflightIntegrationError("after_if_executed is required")
    blocked = [
        str(item["guardrail"])
        for item in snapshot["guardrail_results"]
        if item.get("result") == "BLOCK_REVIEW"
    ]
    unknown = [
        str(item["guardrail"])
        for item in snapshot["guardrail_results"]
        if item.get("result") == "UNKNOWN"
    ]
    if data_status != "CURRENT" and "PORTFOLIO_DATA_STATUS" not in unknown:
        unknown.append("PORTFOLIO_DATA_STATUS")
    return {
        "type": "FEASIBLE_CAPITAL_CONTEXT",
        "risk_snapshot_ref": snapshot_id,
        "captured_at": captured_at,
        "security_code": security_code,
        "data_status": data_status,
        "after_if_executed": {
            "cash_available": after.get("cash_available"),
            "gross_exposure": after.get("gross_exposure"),
            "margin_exposure": after.get("margin_exposure"),
            "position_notional": after.get("position_notional"),
            "position_weight": after.get("position_weight"),
        },
        "defined_rule_blocks": blocked,
        "unknown_constraints": unknown,
        "brokerage_buying_power_verified": False,
        "feasibility": "BLOCKED_BY_DEFINED_RULE" if blocked else "UNKNOWN",
        "trade_action": None,
    }


def japanese_confirmation_model(
    snapshot: Mapping[str, Any],
    *,
    membership_exposure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Japanese-first, display-only pre-trade confirmation model."""
    snapshot_id, captured_at, security_code, data_status = _validate_snapshot(snapshot)
    proposed = snapshot["proposed_action"]
    before = snapshot.get("before") if isinstance(snapshot.get("before"), Mapping) else {}
    after = snapshot.get("after_if_executed") if isinstance(snapshot.get("after_if_executed"), Mapping) else {}
    membership = dict(membership_exposure or {})
    return {
        "title": "売買前のポートフォリオ確認",
        "snapshot_id": snapshot_id,
        "captured_at": captured_at,
        "security_code": security_code,
        "proposed_action": str(proposed.get("action") or ""),
        "data_status": data_status,
        "metrics": [
            {"label": "現在の銘柄金額", "before": before.get("position_notional"), "after": after.get("position_notional")},
            {"label": "買付・売却後の銘柄比率", "before": None, "after": after.get("position_weight")},
            {"label": "現金余力", "before": before.get("cash_available"), "after": after.get("cash_available")},
            {"label": "総エクスポージャー", "before": before.get("gross_exposure"), "after": after.get("gross_exposure")},
            {"label": "信用エクスポージャー", "before": before.get("margin_exposure"), "after": after.get("margin_exposure")},
        ],
        "theme_exposure": membership.get("theme_exposure", []),
        "sector_exposure": membership.get("sector_exposure", []),
        "guardrail_results": [dict(item) for item in snapshot["guardrail_results"]],
        "decision_journal_ref": decision_journal_ref(snapshot),
        "review_context": review_context(snapshot),
        "feasible_capital_context": feasible_capital_context(snapshot),
        "disclaimer": "これは売買指示ではありません。最終判断はオーナーが行います。",
        "trade_action": None,
    }
