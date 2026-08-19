from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

CANONICAL_HOLDINGS_PATH = Path("data/portfolio/current.json")

VALID_SIGNAL_STATES = {"GREEN", "ORANGE", "RED"}
VALID_SENSITIVITIES = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
VALID_YEN_SENSITIVITIES = {"BENEFIT", "NEUTRAL", "HEADWIND", "MIXED", "UNKNOWN"}
VALID_ACTIONS = {"HOLD", "WATCH", "REDUCE_CANDIDATE", "EXIT_REVIEW"}

DEFAULT_SENSITIVITY_DATABASE: dict[str, dict[str, Any]] = {
    "1321": {
        "rate_sensitivity": "MEDIUM",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "MEDIUM",
        "valuation_duration": "MEDIUM",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_early_warning_portfolio_sensitivity_2026-08-13.md"],
    },
    "247A": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "MEDIUM",
        "valuation_duration": "HIGH",
        "balance_sheet_rate_risk": "HIGH",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/247A_ai_robotics.md"],
    },
    "3110": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "BENEFIT",
        "energy_input_sensitivity": "HIGH",
        "valuation_duration": "MEDIUM",
        "balance_sheet_rate_risk": "MEDIUM",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/3110_nittobo.md"],
    },
    "3291": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "NEUTRAL",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "HIGH",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_early_warning_portfolio_sensitivity_2026-08-13.md"],
    },
    "3687": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "HIGH",
        "balance_sheet_rate_risk": "MEDIUM",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/3687_fixstars.md"],
    },
    "3778": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "HIGH",
        "valuation_duration": "HIGH",
        "balance_sheet_rate_risk": "HIGH",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/3778_sakura_internet.md"],
    },
    "4063": {
        "rate_sensitivity": "MEDIUM",
        "yen_sensitivity": "HEADWIND",
        "energy_input_sensitivity": "HIGH",
        "valuation_duration": "MEDIUM",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/4063_shinetsu.md"],
    },
    "4204": {
        "rate_sensitivity": "MEDIUM",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "MEDIUM",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_evidence/4204_sekisui_6965_hamamatsu_batch.md"],
    },
    "4588": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "HIGH",
        "balance_sheet_rate_risk": "HIGH",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/4588_oncolys.md"],
    },
    "4592": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "HIGH",
        "balance_sheet_rate_risk": "HIGH",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/4592_sanbio.md"],
    },
    "5801": {
        "rate_sensitivity": "MEDIUM",
        "yen_sensitivity": "HEADWIND",
        "energy_input_sensitivity": "HIGH",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "MEDIUM",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_early_warning_portfolio_sensitivity_2026-08-13.md"],
    },
    "6356": {
        "rate_sensitivity": "LOW",
        "yen_sensitivity": "NEUTRAL",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_early_warning_portfolio_sensitivity_2026-08-13.md"],
    },
    "6622": {
        "rate_sensitivity": "MEDIUM",
        "yen_sensitivity": "HEADWIND",
        "energy_input_sensitivity": "MEDIUM",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "HIGH",
        "evidence_refs": ["03_Companies/AI/6622_Daihen.md"],
    },
    "6702": {
        "rate_sensitivity": "LOW",
        "yen_sensitivity": "HEADWIND",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "HIGH",
        "evidence_refs": ["01_Portfolio/Transactions/2026-08-19.md"],
    },
    "6965": {
        "rate_sensitivity": "MEDIUM",
        "yen_sensitivity": "HEADWIND",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "MEDIUM",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_evidence/4204_sekisui_6965_hamamatsu_batch.md"],
    },
    "7011": {
        "rate_sensitivity": "LOW",
        "yen_sensitivity": "HEADWIND",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "LOW",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_early_warning_portfolio_sensitivity_2026-08-13.md"],
    },
    "9166": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "NEUTRAL",
        "energy_input_sensitivity": "MEDIUM",
        "valuation_duration": "HIGH",
        "balance_sheet_rate_risk": "HIGH",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_evidence/final5_screen.md"],
    },
    "9348": {
        "rate_sensitivity": "HIGH",
        "yen_sensitivity": "MIXED",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "HIGH",
        "balance_sheet_rate_risk": "HIGH",
        "confidence": "HIGH",
        "evidence_refs": ["06_Research/boj_early_warning_ispace_evidence_2026-08-13.md"],
    },
    "9432": {
        "rate_sensitivity": "LOW",
        "yen_sensitivity": "NEUTRAL",
        "energy_input_sensitivity": "LOW",
        "valuation_duration": "LOW",
        "balance_sheet_rate_risk": "MEDIUM",
        "confidence": "MEDIUM",
        "evidence_refs": ["06_Research/boj_early_warning_portfolio_sensitivity_2026-08-13.md"],
    },
}


def load_canonical_holdings(path: Path | str | None = None) -> dict[str, Any]:
    """Load canonical holdings from portfolio state SSoT (data/portfolio/current.json)."""
    target = Path(path) if path else CANONICAL_HOLDINGS_PATH
    if not target.is_file():
        return {
            "status": "MISSING",
            "as_of": None,
            "positions": [],
            "source_reference": str(target),
            "reason": f"canonical holdings file not found: {target}",
        }
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "INVALID",
            "as_of": None,
            "positions": [],
            "source_reference": str(target),
            "reason": f"canonical holdings file unparseable: {exc}",
        }

    positions = payload.get("positions")
    as_of = payload.get("verification_as_of") or payload.get("as_of")
    status = payload.get("verification_status") or "UNKNOWN"

    if not isinstance(positions, list) or not positions:
        return {
            "status": "MISSING",
            "as_of": as_of,
            "positions": [],
            "source_reference": str(target),
            "reason": "canonical portfolio contains no active positions",
        }

    return {
        "status": status,
        "as_of": as_of,
        "positions": positions,
        "source_reference": str(target),
        "authority": payload.get("authority", "sbi_verified_position_snapshot"),
    }


def evaluate_boj_signal(signal_input: dict[str, Any] | str | Path | None = None) -> dict[str, Any]:
    """Evaluate BOJ signal input and enforce probability-only capping at ORANGE.

    Market-implied probability alone cannot produce RED.
    Primary evidence is required for RED promotion.
    """
    if signal_input is None:
        return {
            "effective_state": "ORANGE",
            "raw_state": "ORANGE",
            "primary_evidence_present": False,
            "probability_only": True,
            "reason": "Default research baseline signal state is ORANGE (Jul PPI +7.2%, import prices +29.1%).",
        }

    if isinstance(signal_input, (str, Path)):
        path = Path(signal_input)
        if not path.is_file():
            return {
                "effective_state": "UNKNOWN",
                "raw_state": "MISSING",
                "primary_evidence_present": False,
                "probability_only": True,
                "reason": f"signal file not found: {path}",
            }
        try:
            signal_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "effective_state": "UNKNOWN",
                "raw_state": "INVALID",
                "primary_evidence_present": False,
                "probability_only": True,
                "reason": f"signal file unparseable: {exc}",
            }
    elif isinstance(signal_input, dict):
        signal_data = signal_input
    else:
        return {
            "effective_state": "UNKNOWN",
            "raw_state": "INVALID",
            "primary_evidence_present": False,
            "probability_only": True,
            "reason": f"unsupported signal input type: {type(signal_input)}",
        }

    raw_state = str(signal_data.get("boj_state") or signal_data.get("signal_state") or "ORANGE").upper()
    if raw_state not in VALID_SIGNAL_STATES:
        raw_state = "ORANGE"

    primary_evidence_present = bool(
        signal_data.get("primary_evidence_present")
        or signal_data.get("primary_evidence")
        or signal_data.get("has_primary_evidence")
    )
    probability_only = bool(
        signal_data.get("probability_only")
        or signal_data.get("market_probability_only")
        or not primary_evidence_present
    )

    reason = str(signal_data.get("reason") or signal_data.get("policy_message") or "")

    effective_state = raw_state
    if raw_state == "RED" and probability_only:
        effective_state = "ORANGE"
        reason = (
            f"[CAPPED_AT_ORANGE] Raw signal requested RED, but market-implied probability alone "
            f"cannot produce RED without primary BOJ evidence. {reason}".strip()
        )

    return {
        "effective_state": effective_state,
        "raw_state": raw_state,
        "primary_evidence_present": primary_evidence_present,
        "probability_only": probability_only,
        "reason": reason if reason else f"Evaluated state {effective_state}",
    }


def determine_position_side(position_type: str) -> str:
    """Map canonical position_type to position_side (LONG or SHORT)."""
    norm = str(position_type or "").strip().lower()
    if norm == "margin_short":
        return "SHORT"
    return "LONG"


def project_position_impact(
    position: dict[str, Any],
    signal_eval: dict[str, Any],
    sensitivity_map: dict[str, Any] | None = None,
    risk_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project BOJ rate hike risk impact on a single portfolio position.

    Enforces invariants:
    - missing/ambiguous sensitivity => UNKNOWN; never coerce UNKNOWN to LOW/HOLD
    - short position side preserved; SHORT must not inherit LONG de-risk action
    - BOJ RED alone cannot produce EXIT_REVIEW
    """
    code = str(position.get("security_code") or "").strip()
    name = str(position.get("security_name") or "").strip()
    pos_type = str(position.get("position_type") or "cash").strip()
    quantity = int(position.get("quantity") or 0)
    position_side = determine_position_side(pos_type)

    effective_signal_state = signal_eval.get("effective_state", "ORANGE")
    ctx = risk_context or {}

    # Lookup company sensitivity evidence
    sens_lookup: dict[str, Any] = {}
    if sensitivity_map and code in sensitivity_map:
        sens_lookup = sensitivity_map[code]
    elif code in DEFAULT_SENSITIVITY_DATABASE:
        sens_lookup = DEFAULT_SENSITIVITY_DATABASE[code]

    rate_sens = str(sens_lookup.get("rate_sensitivity") or "UNKNOWN").upper()
    yen_sens = str(sens_lookup.get("yen_sensitivity") or "UNKNOWN").upper()
    energy_sens = str(sens_lookup.get("energy_input_sensitivity") or "UNKNOWN").upper()
    duration_sens = str(sens_lookup.get("valuation_duration") or "UNKNOWN").upper()
    bs_sens = str(sens_lookup.get("balance_sheet_rate_risk") or "UNKNOWN").upper()

    if rate_sens not in VALID_SENSITIVITIES:
        rate_sens = "UNKNOWN"
    if yen_sens not in VALID_YEN_SENSITIVITIES:
        yen_sens = "UNKNOWN"
    if energy_sens not in VALID_SENSITIVITIES:
        energy_sens = "UNKNOWN"
    if duration_sens not in VALID_SENSITIVITIES:
        duration_sens = "UNKNOWN"
    if bs_sens not in VALID_SENSITIVITIES:
        bs_sens = "UNKNOWN"

    confidence = str(sens_lookup.get("confidence") or "UNKNOWN").upper()
    evidence_refs = sens_lookup.get("evidence_refs") or []

    # Check if sensitivity data is missing/ambiguous
    has_unknown_sensitivity = any(
        s == "UNKNOWN" for s in (rate_sens, yen_sens, energy_sens, duration_sens, bs_sens)
    )
    is_high_sensitivity = any(
        s == "HIGH" for s in (rate_sens, duration_sens, bs_sens, energy_sens)
    )

    # Overlapping risk context flags
    overlapping_market_phase = bool(ctx.get("market_phase_weak") or ctx.get("event_risk"))
    has_thesis_invalidation = bool(ctx.get("thesis_invalidation"))
    has_liquidity_leverage_risk = bool(ctx.get("liquidity_risk") or ctx.get("leverage_risk"))

    # Determine boj_risk_action
    action = "HOLD"
    notes = []

    if position_side == "SHORT":
        # Preserved position_side: short positions must NOT inherit long de-risk actions.
        action = "HOLD" if effective_signal_state == "GREEN" else "WATCH"
        notes.append("Short position side preserved; exempt from long de-risk action.")
    else:
        # LONG position logic
        if effective_signal_state == "GREEN":
            action = "HOLD"
            notes.append("GREEN signal state: no action change from BOJ factor alone.")
        elif effective_signal_state == "ORANGE":
            if has_unknown_sensitivity and not is_high_sensitivity:
                action = "WATCH"
                notes.append("ORANGE signal state with missing/incomplete sensitivity: fail-closed to WATCH.")
            elif is_high_sensitivity:
                if overlapping_market_phase:
                    action = "REDUCE_CANDIDATE"
                    notes.append("ORANGE signal state with HIGH sensitivity and overlapping weak Market Phase/event risk.")
                else:
                    action = "WATCH"
                    notes.append("ORANGE signal state with HIGH sensitivity: set to WATCH.")
            else:
                action = "HOLD"
                notes.append("ORANGE signal state with LOW/MEDIUM sensitivity: HOLD.")
        elif effective_signal_state == "RED":
            if has_unknown_sensitivity and not is_high_sensitivity:
                action = "WATCH"
                notes.append("RED signal state with missing/incomplete sensitivity: fail-closed to WATCH.")
            elif is_high_sensitivity:
                if has_thesis_invalidation or has_liquidity_leverage_risk:
                    action = "EXIT_REVIEW"
                    notes.append("RED signal state with HIGH sensitivity and overlapping thesis invalidation/liquidity/leverage risk.")
                else:
                    action = "REDUCE_CANDIDATE"
                    notes.append("RED signal state with HIGH sensitivity: REDUCE_CANDIDATE review. (BOJ RED alone cannot produce EXIT_REVIEW).")
            else:
                action = "WATCH"
                notes.append("RED signal state with LOW/MEDIUM sensitivity: WATCH.")
        else:
            action = "WATCH"
            notes.append("Unknown BOJ signal state: fail-closed to WATCH.")

    return {
        "security_code": code,
        "security_name": name,
        "position_type": pos_type,
        "position_side": position_side,
        "quantity": quantity,
        "rate_sensitivity": rate_sens,
        "yen_sensitivity": yen_sens,
        "energy_input_sensitivity": energy_sens,
        "valuation_duration": duration_sens,
        "balance_sheet_rate_risk": bs_sens,
        "boj_risk_action": action,
        "evidence_refs": evidence_refs,
        "confidence": confidence,
        "notes": " ".join(notes),
    }


def evaluate_portfolio_boj_impact(
    holdings_input: Path | str | dict[str, Any] | None = None,
    boj_signal_input: Path | str | dict[str, Any] | None = None,
    sensitivity_map: dict[str, Any] | None = None,
    risk_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute deterministic BOJ portfolio impact gate projection."""
    if isinstance(holdings_input, dict):
        holdings_data = holdings_input
    else:
        holdings_data = load_canonical_holdings(holdings_input)

    holdings_status = str(holdings_data.get("status") or "UNKNOWN")
    raw_positions = holdings_data.get("positions") if isinstance(holdings_data.get("positions"), list) else []

    signal_eval = evaluate_boj_signal(boj_signal_input)

    projected_positions = [
        project_position_impact(pos, signal_eval, sensitivity_map=sensitivity_map, risk_context=risk_context)
        for pos in raw_positions
        if isinstance(pos, dict)
    ]

    action_counts = {
        "HOLD": sum(1 for p in projected_positions if p["boj_risk_action"] == "HOLD"),
        "WATCH": sum(1 for p in projected_positions if p["boj_risk_action"] == "WATCH"),
        "REDUCE_CANDIDATE": sum(1 for p in projected_positions if p["boj_risk_action"] == "REDUCE_CANDIDATE"),
        "EXIT_REVIEW": sum(1 for p in projected_positions if p["boj_risk_action"] == "EXIT_REVIEW"),
    }

    as_of = holdings_data.get("as_of") or "2026-08-13"

    return {
        "schema_version": "1.0",
        "as_of": as_of,
        "holdings_status": holdings_status,
        "boj_signal_state": signal_eval["effective_state"],
        "raw_signal_state": signal_eval["raw_state"],
        "primary_evidence_present": signal_eval["primary_evidence_present"],
        "probability_only": signal_eval["probability_only"],
        "signal_reason": signal_eval["reason"],
        "source_references": {
            "holdings_ssot": holdings_data.get("source_reference", str(CANONICAL_HOLDINGS_PATH)),
            "authority": holdings_data.get("authority", "sbi_verified_position_snapshot"),
        },
        "summary": {
            "total_positions": len(projected_positions),
            "actions": action_counts,
        },
        "positions": projected_positions,
        "guardrails": {
            "no_auto_order_generation": True,
            "no_owner_authority_mutation": True,
            "probability_only_red_blocked": True,
            "short_side_direction_preserved": True,
            "missing_sensitivity_fail_closed": True,
            "issue_79_untouched": True,
            "auto_green_execution_off": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="BOJ Portfolio Impact Gate v1")
    parser.add_argument("--holdings", help="Path to canonical holdings JSON")
    parser.add_argument("--signal", help="Path to BOJ signal JSON")
    parser.add_argument("--out", help="Output path for JSON result")
    args = parser.parse_args()

    result = evaluate_portfolio_boj_impact(
        holdings_input=args.holdings,
        boj_signal_input=args.signal,
    )

    output_json = json.dumps(result, ensure_ascii=False, indent=2) + "\n"

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
    else:
        sys.stdout.write(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
