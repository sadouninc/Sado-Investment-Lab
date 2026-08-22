from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

CANONICAL_HOLDINGS_PATH = Path("data/portfolio/current.json")
CANONICAL_RESEARCH_DIR = Path("06_Research/boj_evidence")

VALID_SIGNAL_STATES = {"GREEN", "ORANGE", "RED"}
VALID_SENSITIVITIES = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
VALID_YEN_SENSITIVITIES = {"BENEFIT", "NEUTRAL", "HEADWIND", "MIXED", "UNKNOWN"}


def parse_markdown_yaml_block(text: str) -> dict[str, str]:
    """Extract YAML key-values from markdown research evidence files."""
    extracted = {}
    yaml_block_match = re.search(r"```yaml\s*\n(.*?)\n```", text, re.DOTALL)
    block_text = yaml_block_match.group(1) if yaml_block_match else text

    for line in block_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            extracted[key.strip().lower()] = val.strip().strip("'\"").upper()
    return extracted


def load_canonical_research_sensitivities(research_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Dynamically parse canonical research evidence artifacts read-only without duplicating facts in code."""
    target_dir = Path(research_dir) if research_dir else CANONICAL_RESEARCH_DIR
    sensitivities: dict[str, dict[str, Any]] = {}

    if not target_dir.is_dir():
        return sensitivities

    for file_path in target_dir.glob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError:
            continue

        # Extract stock code from filename (e.g. 3778_sakura_internet.md => 3778) or header
        code_match = re.match(r"^(\d{3,4}[A-Z]?)_", file_path.name)
        if not code_match:
            code_header = re.search(r"^#\s*(\d{3,4}[A-Z]?)\s", content, re.MULTILINE)
            code = code_header.group(1) if code_header else None
        else:
            code = code_match.group(1)

        if not code:
            continue

        yaml_data = parse_markdown_yaml_block(content)
        if yaml_data:
            sensitivities[code] = {
                "rate_sensitivity": yaml_data.get("rate_sensitivity", "UNKNOWN"),
                "yen_sensitivity": yaml_data.get("yen_sensitivity", "UNKNOWN"),
                "energy_input_sensitivity": yaml_data.get("energy_input_sensitivity", "UNKNOWN"),
                "valuation_duration": yaml_data.get("valuation_duration", "UNKNOWN"),
                "balance_sheet_rate_risk": yaml_data.get("balance_sheet_rate_risk", "UNKNOWN"),
                "confidence": yaml_data.get("confidence", "UNKNOWN"),
                "evidence_refs": [str(file_path)],
            }

    return sensitivities


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

    Fail-closed rule: Missing or unparseable signal, or unknown boj_state, remains UNKNOWN.
    UNKNOWN != PASS/ORANGE.
    """
    if signal_input is None:
        # Check if canonical ledger file exists
        ledger_file = Path("06_Research/boj_evidence/boj_observation_ledger_512.jsonl")
        if ledger_file.is_file():
            try:
                lines = [line.strip() for line in ledger_file.read_text(encoding="utf-8").splitlines() if line.strip()]
                if lines:
                    last_record = json.loads(lines[-1])
                    return evaluate_boj_signal(last_record)
            except (OSError, json.JSONDecodeError):
                pass

        return {
            "effective_state": "UNKNOWN",
            "raw_state": "MISSING",
            "primary_evidence_present": False,
            "probability_only": True,
            "reason": "No valid canonical BOJ signal input provided; failing closed to UNKNOWN.",
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

    raw_state_str = signal_data.get("boj_state") or signal_data.get("signal_state")
    if not raw_state_str or not isinstance(raw_state_str, str):
        return {
            "effective_state": "UNKNOWN",
            "raw_state": "UNKNOWN",
            "primary_evidence_present": False,
            "probability_only": True,
            "reason": "Missing or non-string boj_state in signal payload; failing closed to UNKNOWN.",
        }

    raw_state = raw_state_str.strip().upper()
    if raw_state not in VALID_SIGNAL_STATES:
        return {
            "effective_state": "UNKNOWN",
            "raw_state": raw_state,
            "primary_evidence_present": False,
            "probability_only": True,
            "reason": f"Unknown boj_state '{raw_state}'; failing closed to UNKNOWN.",
        }

    primary_evidence_present = bool(
        signal_data.get("primary_evidence_present")
        or signal_data.get("primary_evidence")
        or signal_data.get("has_primary_evidence")
        or (signal_data.get("interpretation") and isinstance(signal_data["interpretation"], dict) and signal_data["interpretation"].get("red_gate") == "MET")
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
    """Map canonical position_type to position_side (LONG, SHORT, or UNKNOWN)."""
    norm = str(position_type or "").strip().lower()
    if norm in {"cash", "margin_long"}:
        return "LONG"
    if norm in {"margin_short"}:
        return "SHORT"
    return "UNKNOWN"


def parse_position_quantity(raw_qty: Any) -> tuple[int | str | None, bool]:
    """Safely parse position quantity without raising ValueError or TypeError.

    Returns (quantity_value, is_valid_integer).
    """
    if raw_qty is None:
        return 0, True
    if isinstance(raw_qty, int) and not isinstance(raw_qty, bool):
        return raw_qty, True
    if isinstance(raw_qty, float):
        if raw_qty.is_integer():
            return int(raw_qty), True
        return str(raw_qty), False
    if isinstance(raw_qty, str):
        cleaned = raw_qty.strip()
        if not cleaned:
            return 0, True
        try:
            return int(cleaned), True
        except ValueError:
            return cleaned, False
    return str(raw_qty), False


def resolve_position_risk_context(code: str, risk_context: dict[str, Any] | None) -> dict[str, Any]:
    """Extract position-specific risk context keyed by security code to prevent global risk leaks."""
    if not risk_context or not isinstance(risk_context, dict):
        return {}

    # Check if risk_context is a dictionary of security codes
    if code in risk_context and isinstance(risk_context[code], dict):
        return risk_context[code]

    # Check if risk_context has a "positions" sub-dictionary
    positions_map = risk_context.get("positions")
    if isinstance(positions_map, dict) and code in positions_map and isinstance(positions_map[code], dict):
        return positions_map[code]

    # Check if risk_context specifies a target_security
    if risk_context.get("target_security") == code:
        return risk_context

    return {}


def project_position_impact(
    position: dict[str, Any],
    signal_eval: dict[str, Any],
    sensitivity_map: dict[str, Any] | None = None,
    risk_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project BOJ rate hike risk impact on a single portfolio position.

    Enforces invariants:
    - missing/ambiguous sensitivity => UNKNOWN; never coerce UNKNOWN to LOW/HOLD
    - incomplete sensitivity facts (any UNKNOWN dimension) cannot produce REDUCE_CANDIDATE or EXIT_REVIEW
    - short position side preserved; SHORT must not inherit LONG de-risk action
    - unknown position_type => UNKNOWN position side; fails closed to WATCH/HOLD
    - malformed/non-integer quantity => preserves raw value for provenance, fails closed to WATCH/HOLD
    - BOJ RED alone cannot produce EXIT_REVIEW
    - risk_context is scoped per position identity to prevent global risk leakage
    """
    code = str(position.get("security_code") or "").strip()
    name = str(position.get("security_name") or "").strip()
    pos_type = str(position.get("position_type") or "").strip()
    quantity, qty_valid = parse_position_quantity(position.get("quantity"))
    position_side = determine_position_side(pos_type)

    effective_signal_state = signal_eval.get("effective_state", "UNKNOWN")
    pos_risk_ctx = resolve_position_risk_context(code, risk_context)

    # Lookup company sensitivity evidence dynamically
    sens_lookup: dict[str, Any] = {}
    if sensitivity_map and code in sensitivity_map:
        sens_lookup = sensitivity_map[code]

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

    # Check sensitivity completeness
    has_unknown_sensitivity = any(
        s == "UNKNOWN" for s in (rate_sens, yen_sens, energy_sens, duration_sens, bs_sens)
    )
    is_high_sensitivity = any(
        s == "HIGH" for s in (rate_sens, duration_sens, bs_sens, energy_sens)
    )

    # Position-specific overlapping risk context flags
    overlapping_market_phase = bool(pos_risk_ctx.get("market_phase_weak") or pos_risk_ctx.get("event_risk"))
    has_thesis_invalidation = bool(pos_risk_ctx.get("thesis_invalidation"))
    has_liquidity_leverage_risk = bool(pos_risk_ctx.get("liquidity_risk") or pos_risk_ctx.get("leverage_risk"))

    # Determine boj_risk_action
    notes = []

    if not qty_valid:
        action = "HOLD" if effective_signal_state == "GREEN" else "WATCH"
        notes.append(f"Malformed quantity input '{quantity}'; failing closed to WATCH.")
    elif position_side == "UNKNOWN":
        action = "HOLD" if effective_signal_state == "GREEN" else "WATCH"
        notes.append("Unknown position_type/side; failing closed to WATCH.")
    elif position_side == "SHORT":
        # Preserved position_side: short positions must NOT inherit long de-risk actions.
        action = "HOLD" if effective_signal_state == "GREEN" else "WATCH"
        notes.append("Short position side preserved; exempt from long de-risk action.")
    else:
        # LONG position logic
        if effective_signal_state == "GREEN":
            action = "HOLD"
            notes.append("GREEN signal state: no action change from BOJ factor alone.")
        elif effective_signal_state in {"ORANGE", "RED"}:
            if has_unknown_sensitivity:
                # Incomplete sensitivity CANNOT produce REDUCE_CANDIDATE or EXIT_REVIEW
                action = "WATCH"
                notes.append(f"{effective_signal_state} signal state with incomplete/unknown sensitivity facts: failing closed to WATCH.")
            elif is_high_sensitivity:
                if effective_signal_state == "ORANGE":
                    if overlapping_market_phase:
                        action = "REDUCE_CANDIDATE"
                        notes.append("ORANGE signal state with HIGH sensitivity and overlapping weak Market Phase/event risk.")
                    else:
                        action = "WATCH"
                        notes.append("ORANGE signal state with HIGH sensitivity: set to WATCH.")
                else:  # RED
                    if has_thesis_invalidation or has_liquidity_leverage_risk:
                        action = "EXIT_REVIEW"
                        notes.append("RED signal state with HIGH sensitivity and position-specific thesis invalidation/liquidity/leverage risk.")
                    else:
                        action = "REDUCE_CANDIDATE"
                        notes.append("RED signal state with HIGH sensitivity: REDUCE_CANDIDATE review. (BOJ RED alone cannot produce EXIT_REVIEW).")
            else:
                action = "HOLD" if effective_signal_state == "ORANGE" else "WATCH"
                notes.append(f"{effective_signal_state} signal state with LOW/MEDIUM sensitivity: {action}.")
        else:
            action = "WATCH"
            notes.append("Unknown BOJ signal state: failing closed to WATCH.")

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
    research_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Execute deterministic BOJ portfolio impact gate projection."""
    if isinstance(holdings_input, dict):
        holdings_data = holdings_input
    else:
        holdings_data = load_canonical_holdings(holdings_input)

    holdings_status = str(holdings_data.get("status") or "UNKNOWN")
    raw_positions = holdings_data.get("positions") if isinstance(holdings_data.get("positions"), list) else []

    signal_eval = evaluate_boj_signal(boj_signal_input)

    # Dynamically load sensitivity evidence if not explicitly passed
    effective_sens_map = sensitivity_map if sensitivity_map is not None else load_canonical_research_sensitivities(research_dir)

    projected_positions = [
        project_position_impact(pos, signal_eval, sensitivity_map=effective_sens_map, risk_context=risk_context)
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
            "unknown_signal_fail_closed": True,
            "position_scoped_risk_context": True,
            "malformed_quantity_fail_closed": True,
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
