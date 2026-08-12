from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from scripts.risk_preflight_what_if import WhatIfIntentError, preview_what_if


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTFOLIO = ROOT / "data" / "portfolio" / "current.json"


def _optional_positive_float(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    number = float(value)
    if number <= 0:
        raise ValueError("optional numeric context must be positive")
    return number


def build_runtime_result(
    *,
    security_code: str,
    action: str,
    quantity: int,
    price: float,
    account_type: str = "UNKNOWN",
    portfolio_path: Path = DEFAULT_PORTFOLIO,
    portfolio_equity: float | None = None,
    cash_available: float | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    captured_at = captured_at or datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
    intent = {
        "security_code": security_code,
        "action": action,
        "quantity": quantity,
        "price": price,
        "account_type": account_type,
        "price_source": "OWNER_WHAT_IF_INPUT",
        "price_as_of": captured_at,
    }

    try:
        return preview_what_if(
            portfolio,
            intent,
            captured_at=captured_at,
            market_prices={security_code: price},
            portfolio_equity=portfolio_equity,
            cash_available=cash_available,
            rules={},
        )
    except WhatIfIntentError as exc:
        return {
            "state": exc.state,
            "ephemeral": True,
            "is_order": False,
            "intent": intent,
            "message": str(exc),
            "risk_preflight": None,
            "canonical_mutations": [],
        }


def attach_runtime_telemetry(
    result: dict[str, Any],
    *,
    calculation_started_at: str,
    calculation_completed_at: str,
    calculation_duration_ms: float,
    github_run_id: str | None = None,
    github_run_attempt: str | None = None,
) -> dict[str, Any]:
    enriched = dict(result)
    enriched["runtime_telemetry"] = {
        "calculation_started_at": calculation_started_at,
        "calculation_completed_at": calculation_completed_at,
        "calculation_duration_ms": round(calculation_duration_ms, 3),
        "github_run_id": github_run_id or None,
        "github_run_attempt": github_run_attempt or None,
        "scope": "OPS_DIAGNOSTICS_ONLY",
        "canonical_mutation": False,
    }
    return enriched


def _summary_lines(result: dict[str, Any]) -> list[str]:
    intent = result.get("intent") or {}
    lines = [
        "# 売買前 What-if 結果",
        "",
        f"- 状態: `{result.get('state', 'UNKNOWN')}`",
        f"- 対象: `{intent.get('security_code', 'UNKNOWN')}`",
        f"- 仮定: `{intent.get('action', 'UNKNOWN')} {intent.get('quantity', '?')}株 @ {intent.get('price', '?')}円`",
        f"- 口座文脈: `{intent.get('account_type', 'UNKNOWN')}`",
        "- 実注文: **行いません**",
        "- Canonical変更: **なし**",
        "",
    ]
    if result.get("message"):
        lines += ["## 確認が必要", "", str(result["message"]), ""]
    risk = result.get("risk_preflight") or {}
    before = risk.get("before") or {}
    after = risk.get("after_if_executed") or {}
    if risk:
        lines += [
            "## Before → After",
            "",
            f"- Position notional: `{before.get('position_notional')}` → `{after.get('position_notional')}`",
            f"- Position weight: `{before.get('position_weight')}` → `{after.get('position_weight')}`",
            f"- Cash: `{before.get('cash_available')}` → `{after.get('cash_available')}`",
            f"- Gross exposure: `{before.get('gross_exposure')}` → `{after.get('gross_exposure')}`",
            f"- Margin exposure: `{before.get('margin_exposure')}` → `{after.get('margin_exposure')}`",
            "",
            "不足値は0へ補完せず `null` / `UNKNOWN` のまま保持します。",
        ]
    telemetry = result.get("runtime_telemetry") or {}
    if telemetry:
        lines += [
            "",
            "## Runtime telemetry（運用診断のみ）",
            "",
            f"- Calculation started: `{telemetry.get('calculation_started_at')}`",
            f"- Calculation completed: `{telemetry.get('calculation_completed_at')}`",
            f"- Calculation duration: `{telemetry.get('calculation_duration_ms')} ms`",
            f"- GitHub run id: `{telemetry.get('github_run_id')}`",
            "- Investment Decision / Portfolioへは保存しません。",
        ]
    return lines


def write_outputs(result: dict[str, Any], *, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(_summary_lines(result)) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run #307 ephemeral pre-trade What-if using canonical #233 calculator")
    parser.add_argument("--security-code", required=True)
    parser.add_argument("--action", required=True, choices=("BUY", "SELL"))
    parser.add_argument("--quantity", required=True, type=int)
    parser.add_argument("--price", required=True, type=float)
    parser.add_argument("--account-type", default="UNKNOWN", choices=("CASH", "MARGIN", "UNKNOWN"))
    parser.add_argument("--portfolio-equity")
    parser.add_argument("--cash-available")
    parser.add_argument("--portfolio", type=Path, default=DEFAULT_PORTFOLIO)
    parser.add_argument("--output", type=Path, default=Path("artifacts/risk-preflight-what-if/result.json"))
    args = parser.parse_args()

    clock = ZoneInfo("Asia/Tokyo")
    calculation_started_at = datetime.now(clock).isoformat(timespec="milliseconds")
    started = perf_counter()

    try:
        portfolio_equity = _optional_positive_float(args.portfolio_equity)
        cash_available = _optional_positive_float(args.cash_available)
    except (TypeError, ValueError) as exc:
        result = {
            "state": "INVALID_INPUT",
            "ephemeral": True,
            "is_order": False,
            "message": str(exc),
            "canonical_mutations": [],
        }
    else:
        result = build_runtime_result(
            security_code=args.security_code,
            action=args.action,
            quantity=args.quantity,
            price=args.price,
            account_type=args.account_type,
            portfolio_path=args.portfolio,
            portfolio_equity=portfolio_equity,
            cash_available=cash_available,
        )

    calculation_completed_at = datetime.now(clock).isoformat(timespec="milliseconds")
    result = attach_runtime_telemetry(
        result,
        calculation_started_at=calculation_started_at,
        calculation_completed_at=calculation_completed_at,
        calculation_duration_ms=(perf_counter() - started) * 1000,
        github_run_id=os.environ.get("GITHUB_RUN_ID"),
        github_run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT"),
    )
    write_outputs(result, output_path=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
