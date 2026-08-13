from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.money_flow_history import load_history
from scripts.policy_lead_time_v2 import evaluate_policy_lead_time_v2
from scripts.policy_state_sequence import summarize_policy_state_sequence

DEFAULT_THEME_ID = "theme:fusion-energy-component-supply-chain"
DEFAULT_THEME_CONFIG = "data/config/money-flow-themes-v1.json"
DEFAULT_HISTORY = "data/generated/public/money-flow/history.jsonl"
DEFAULT_OUTPUT = "data/generated/public/money-flow/policy-lead-time-fusion-v2.json"

POLICY_CHECKPOINTS = (
    (
        "2023-04-14",
        "STRATEGY_INITIAL",
        "Fusion Energy Innovation Strategy initial adoption",
        "https://www8.cao.go.jp/cstp/tougosenryaku/15kai/15kai.html",
    ),
    (
        "2025-06-04",
        "STRATEGY_REVISION",
        "Fusion Energy Innovation Strategy revision",
        "https://www8.cao.go.jp/cstp/tougosenryaku/23kai/23kai.html",
    ),
    (
        "2026-04-08",
        "SOCIAL_IMPLEMENTATION_PATH",
        "Social implementation pathway for fusion energy",
        "https://www8.cao.go.jp/cstp/fusion/fusion_wg/3kai/3kai.html",
    ),
    (
        "2026-07-07",
        "INVESTMENT_ROADMAP_DEMO_DESIGN",
        "Public-private investment roadmap / power demonstration design",
        "https://www8.cao.go.jp/cstp/fusion/13kai/13kai.html",
    ),
    (
        "2026-07-21",
        "GROWTH_STRATEGY_ROADMAP",
        "Japan Growth Strategy / fusion investment roadmap",
        "https://www5.cao.go.jp/keizai-shimon/kaigi/minutes/2026/0721_shiryo03.pdf",
    ),
)


class FusionPolicyLeadTimeError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FusionPolicyLeadTimeError(f"{path} must contain a JSON object")
    return payload


def _theme_entry(theme_config: Mapping[str, Any], theme_id: str) -> dict[str, Any]:
    matches = [row for row in theme_config.get("themes") or [] if str(row.get("id")) == theme_id]
    if len(matches) != 1:
        raise FusionPolicyLeadTimeError(f"theme config must contain exactly one {theme_id}")
    return dict(matches[0])


def _first_state(sequence: Mapping[str, Any], state: str, *, reliable: bool) -> str | None:
    for row in sequence.get("sequence") or []:
        if row.get("state") != state:
            continue
        if reliable and row.get("reliable") is not True:
            continue
        return str(row["as_of"])
    return None


def _checkpoint_evaluation(
    *, history: list[dict[str, Any]], theme_id: str, checkpoint: str, base_limitations: list[str]
) -> dict[str, Any]:
    sequence = summarize_policy_state_sequence(history, policy_t0=checkpoint, theme_id=theme_id)
    limitations = set(base_limitations)
    limitations.add("BENCHMARK_PROXY")

    reliable_warming = _first_state(sequence, "WARMING", reliable=True)
    reliable_inflow = _first_state(sequence, "INFLOW", reliable=True)
    if reliable_warming is None and reliable_inflow is None:
        limitations.add("RELIABLE_MARKET_SIGNAL_NOT_OBSERVED")
        quality = "LIMITED"
    else:
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


def build_fusion_policy_lead_time_v2(
    *, history: list[dict[str, Any]], theme_config: Mapping[str, Any], theme_id: str = DEFAULT_THEME_ID
) -> dict[str, Any]:
    entry = _theme_entry(theme_config, theme_id)
    members = [dict(member) for member in entry.get("members") or []]
    expected_codes = {"7011", "5803", "5801", "5802", "7013"}
    if {str(member.get("security_code")) for member in members} != expected_codes:
        raise FusionPolicyLeadTimeError("Fusion canonical membership does not match Issue #459 Membership Gate Authority")

    base_limitations = [str(value).upper() for value in (entry.get("limitations") or [])]
    required_limitations = {
        "RETROSPECTIVE_MEMBERSHIP",
        "THEME_SCOPE_PROXY",
        "CONGLOMERATE_EXPOSURE",
        "NARROW_MEMBERSHIP",
    }
    if not required_limitations.issubset(set(base_limitations)):
        raise FusionPolicyLeadTimeError("Fusion canonical membership limitations do not match Issue #459 Authority")

    checkpoints = []
    for checkpoint, stage, label, source_ref in POLICY_CHECKPOINTS:
        checkpoints.append(
            {
                "date": checkpoint,
                "policy_stage": stage,
                "label": label,
                "source_ref": source_ref,
                **_checkpoint_evaluation(
                    history=history,
                    theme_id=theme_id,
                    checkpoint=checkpoint,
                    base_limitations=base_limitations,
                ),
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
        "limitations": sorted(set(base_limitations + ["BENCHMARK_PROXY"])),
        "policy_checkpoints": checkpoints,
        "policy_evidence_in_market_score": False,
        "source_refs": {
            "membership": "Issue #459 Membership Gate",
            "policy_watchlist": "Issue #154",
            "money_flow_history": DEFAULT_HISTORY,
            "theme_config": DEFAULT_THEME_CONFIG,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Fusion Policy Lead-Time v2 artifact")
    parser.add_argument("--history", default=DEFAULT_HISTORY)
    parser.add_argument("--theme-config", default=DEFAULT_THEME_CONFIG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_fusion_policy_lead_time_v2(
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
