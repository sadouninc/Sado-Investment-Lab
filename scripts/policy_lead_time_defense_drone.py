from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from scripts.money_flow_history import load_history
from scripts.policy_lead_time_v2 import evaluate_policy_lead_time_v2
from scripts.policy_state_sequence import summarize_policy_state_sequence

DEFAULT_THEME_ID = "theme:defense-drone-small-mass-domestic"
DEFAULT_THEME_CONFIG = "data/config/money-flow-themes-v1.json"
DEFAULT_HISTORY = "data/generated/public/money-flow/history.jsonl"
DEFAULT_OUTPUT = "data/generated/public/money-flow/policy-lead-time-defense-drone-v2.json"
TWO_STOCK_THEME_FROM = "2024-11-29"

POLICY_CHECKPOINTS = (
    ("2022-12-16", "STRATEGY", "National Defense Strategy / Defense Buildup Program"),
    ("2024-10-02", "PROCUREMENT_SIGNAL", "First small attack UAV procurement signal"),
    ("2026-05-12", "DOMESTIC_MASS_PRODUCTION", "Domestic mass-production / stable procurement policy"),
    ("2026-07-01", "RAPID_ACQUISITION_WINDOW", "Rapid acquisition / demonstration phase"),
)


class DefenseDronePolicyLeadTimeError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DefenseDronePolicyLeadTimeError(f"{path} must contain a JSON object")
    return payload


def _theme_entry(theme_config: Mapping[str, Any], theme_id: str) -> dict[str, Any]:
    matches = [row for row in theme_config.get("themes") or [] if str(row.get("id")) == theme_id]
    if len(matches) != 1:
        raise DefenseDronePolicyLeadTimeError(f"theme config must contain exactly one {theme_id}")
    return dict(matches[0])


def _first_state(sequence: Mapping[str, Any], state: str, *, reliable: bool) -> str | None:
    for row in sequence.get("sequence") or []:
        if row.get("state") != state:
            continue
        if reliable and row.get("reliable") is not True:
            continue
        return str(row["as_of"])
    return None


def _phase(checkpoint: str) -> str:
    return "TWO_STOCK_THEME" if checkpoint >= TWO_STOCK_THEME_FROM else "COMPANY_PROXY_ACSL_ONLY"


def _checkpoint_evaluation(
    *, history: list[dict[str, Any]], theme_id: str, checkpoint: str, base_limitations: list[str]
) -> dict[str, Any]:
    sequence = summarize_policy_state_sequence(history, policy_t0=checkpoint, theme_id=theme_id)
    phase = _phase(checkpoint)
    limitations = set(base_limitations)
    limitations.update({"RETROSPECTIVE_MEMBERSHIP", "NARROW_MEMBERSHIP", "BENCHMARK_PROXY"})

    reliable_warming = _first_state(sequence, "WARMING", reliable=True)
    reliable_inflow = _first_state(sequence, "INFLOW", reliable=True)
    if phase != "TWO_STOCK_THEME":
        limitations.update({"COMPANY_PROXY_ONLY", "THEME_BREADTH_NOT_AVAILABLE"})
        quality = "LIMITED"
    elif reliable_warming is None and reliable_inflow is None:
        limitations.add("RELIABLE_MARKET_SIGNAL_NOT_OBSERVED")
        quality = "LIMITED"
    else:
        # RETROSPECTIVE_MEMBERSHIP and NARROW_MEMBERSHIP remain explicit caveats,
        # but do not erase an otherwise reliable observed market relationship.
        quality = "OK"

    evaluation = evaluate_policy_lead_time_v2(
        {
            "policy_t0": checkpoint,
            "raw_first_warming_date": _first_state(sequence, "WARMING", reliable=False),
            "raw_first_inflow_date": _first_state(sequence, "INFLOW", reliable=False),
            "reliable_first_warming_date": reliable_warming,
            "reliable_first_inflow_date": reliable_inflow,
            "data_quality": quality,
            "limitations": sorted(limitations),
            "post_policy_persistence": bool(sequence["post_policy_persistence"]),
            "post_policy_reacceleration": bool(sequence["post_policy_reacceleration"]),
        }
    )
    return {
        "phase": phase,
        "evaluation": evaluation,
        "sequence_summary": {
            "pre_policy_state": sequence["pre_policy_state"],
            "state_at_or_before_policy": sequence["state_at_or_before_policy"],
            "reliable_first_post_policy_warming": sequence["reliable_first_post_policy_warming"],
            "reliable_first_post_policy_inflow": sequence["reliable_first_post_policy_inflow"],
            "reliable_strongest_pre_policy_state": sequence["reliable_strongest_pre_policy_state"],
            "reliable_strongest_post_policy_state": sequence["reliable_strongest_post_policy_state"],
        },
    }


def build_defense_drone_policy_lead_time_v2(
    *, history: list[dict[str, Any]], theme_config: Mapping[str, Any], theme_id: str = DEFAULT_THEME_ID
) -> dict[str, Any]:
    entry = _theme_entry(theme_config, theme_id)
    members = [dict(member) for member in entry.get("members") or []]
    if {str(member.get("security_code")) for member in members} != {"278A", "6232"}:
        raise DefenseDronePolicyLeadTimeError("Defense Drone canonical membership must be Terra Drone + ACSL")

    base_limitations = [str(value).upper() for value in (entry.get("limitations") or [])]
    checkpoints = []
    for checkpoint, stage, label in POLICY_CHECKPOINTS:
        result = _checkpoint_evaluation(
            history=history,
            theme_id=theme_id,
            checkpoint=checkpoint,
            base_limitations=base_limitations,
        )
        checkpoints.append(
            {
                "date": checkpoint,
                "policy_stage": stage,
                "label": label,
                **result,
            }
        )

    return {
        "schema_version": 1,
        "theme_id": theme_id,
        "theme_name": entry.get("name"),
        "membership_as_of": entry.get("membership_as_of"),
        "membership_version": entry.get("membership_version"),
        "membership_authority": entry.get("authority"),
        "members": members,
        "two_stock_theme_from": TWO_STOCK_THEME_FROM,
        "pre_listing_phase": "COMPANY_PROXY_ACSL_ONLY",
        "limitations": sorted(set(base_limitations + ["RETROSPECTIVE_MEMBERSHIP", "NARROW_MEMBERSHIP", "BENCHMARK_PROXY"])),
        "policy_checkpoints": checkpoints,
        "policy_evidence_in_market_score": False,
        "source_refs": {
            "membership": "Issue #259",
            "company_evidence": "Issue #321",
            "money_flow_history": DEFAULT_HISTORY,
            "theme_config": DEFAULT_THEME_CONFIG,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Defense Drone Policy Lead-Time v2 validation artifact")
    parser.add_argument("--history", default=DEFAULT_HISTORY)
    parser.add_argument("--theme-config", default=DEFAULT_THEME_CONFIG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_defense_drone_policy_lead_time_v2(
        history=load_history(Path(args.history)),
        theme_config=_load_json(Path(args.theme_config)),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
