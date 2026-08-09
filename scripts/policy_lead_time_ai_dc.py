from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from scripts.money_flow_history import load_history
from scripts.policy_lead_time_v2 import evaluate_policy_lead_time_v2
from scripts.policy_state_sequence import summarize_policy_state_sequence

DEFAULT_THEME_ID = "theme:ai-data-center-power-infrastructure"
DEFAULT_POLICY_T0 = "2024-10-04"


class PolicyLeadTimeAIDCError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PolicyLeadTimeAIDCError(f"{path} must contain a JSON object")
    return payload


def _first_reliable(sequence: Mapping[str, Any], state: str) -> str | None:
    for row in sequence.get("sequence") or []:
        if row.get("reliable") is True and row.get("state") == state:
            return str(row["as_of"])
    return None


def build_ai_dc_policy_lead_time_v2(
    *,
    history: list[dict[str, Any]],
    v1_lead_time: Mapping[str, Any],
    theme_id: str = DEFAULT_THEME_ID,
    policy_t0: str = DEFAULT_POLICY_T0,
) -> dict[str, Any]:
    """Build the persisted AI/DC v2 evaluation without rewriting v1 or history."""
    v1 = deepcopy(dict(v1_lead_time))
    if str(v1.get("theme_id") or "") != theme_id:
        raise PolicyLeadTimeAIDCError("v1 theme_id does not match requested theme")
    if str(v1.get("policy_t0") or "") != policy_t0:
        raise PolicyLeadTimeAIDCError("v1 policy_t0 does not match requested checkpoint")

    sequence = summarize_policy_state_sequence(history, policy_t0=policy_t0, theme_id=theme_id)
    limitations = sorted({str(value).upper() for value in (v1.get("limitations") or [])})
    data_quality = "LIMITED" if limitations else "OK"

    evaluation = evaluate_policy_lead_time_v2(
        {
            "policy_t0": policy_t0,
            "raw_first_warming_date": v1.get("first_warming_date"),
            "raw_first_inflow_date": v1.get("first_inflow_date"),
            "reliable_first_warming_date": _first_reliable(sequence, "WARMING"),
            "reliable_first_inflow_date": _first_reliable(sequence, "INFLOW"),
            "data_quality": data_quality,
            "limitations": limitations,
            "post_policy_persistence": sequence["post_policy_persistence"],
            "post_policy_reacceleration": sequence["post_policy_reacceleration"],
        }
    )
    return {
        "theme_id": theme_id,
        "evaluation": evaluation,
        "sequence_summary": {
            "pre_policy_state": sequence["pre_policy_state"],
            "state_at_or_before_policy": sequence["state_at_or_before_policy"],
            "first_post_policy_warming": sequence["first_post_policy_warming"],
            "first_post_policy_inflow": sequence["first_post_policy_inflow"],
            "reliable_first_post_policy_warming": sequence["reliable_first_post_policy_warming"],
            "reliable_first_post_policy_inflow": sequence["reliable_first_post_policy_inflow"],
            "strongest_pre_policy_state": sequence["strongest_pre_policy_state"],
            "strongest_post_policy_state": sequence["strongest_post_policy_state"],
            "reliable_strongest_pre_policy_state": sequence["reliable_strongest_pre_policy_state"],
            "reliable_strongest_post_policy_state": sequence["reliable_strongest_post_policy_state"],
        },
        "source_refs": {
            "money_flow_history": "data/generated/public/money-flow/history.jsonl",
            "v1_lead_time": "data/generated/public/money-flow/policy-lead-time-ai-dc.json",
        },
        "v1_preserved": True,
        "policy_evidence_in_market_score": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AI/DC Policy Lead-Time v2 artifact")
    parser.add_argument("--history", default="data/generated/public/money-flow/history.jsonl")
    parser.add_argument("--v1", default="data/generated/public/money-flow/policy-lead-time-ai-dc.json")
    parser.add_argument("--output", default="data/generated/public/money-flow/policy-lead-time-ai-dc-v2.json")
    args = parser.parse_args()

    payload = build_ai_dc_policy_lead_time_v2(
        history=load_history(Path(args.history)),
        v1_lead_time=_load_json(Path(args.v1)),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
