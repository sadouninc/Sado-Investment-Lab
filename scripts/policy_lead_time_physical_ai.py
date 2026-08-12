from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.money_flow_history import load_history
from scripts.policy_lead_time_v2 import evaluate_policy_lead_time_v2
from scripts.policy_state_sequence import summarize_policy_state_sequence

DEFAULT_THEME_ID = "theme:physical-ai-robotics-core"
DEFAULT_THEME_CONFIG = "data/config/money-flow-themes-v1.json"
DEFAULT_HISTORY = "data/generated/public/money-flow/history.jsonl"
DEFAULT_OUTPUT = "data/generated/public/money-flow/policy-lead-time-physical-ai-v2.json"

POLICY_CHECKPOINTS = (
    (
        "2026-03-24",
        "R&D_CALL",
        "NEDO multimodal foundation-model program call",
        "https://www.nedo.go.jp/koubo/CD2_100431.html",
    ),
    (
        "2026-05-14",
        "R&D_SELECTION",
        "NEDO GENIAC robot foundation-model selection",
        "https://www.nedo.go.jp/koubo/CD3_100427.html",
    ),
    (
        "2026-05-27",
        "STRATEGY_SOCIAL_IMPLEMENTATION",
        "AI Robotics Strategy update / social implementation",
        "https://www.meti.go.jp/policy/mono_info_service/mono/robot/index.html",
    ),
    (
        "2026-06-30",
        "R&D_SELECTION_MULTIYEAR",
        "NEDO multimodal foundation-model implementer selection",
        "https://www.nedo.go.jp/koubo/CD3_100431.html",
    ),
    (
        "2026-07-21",
        "INVESTMENT_ROADMAP_DEMAND_CREATION",
        "Japan Growth Strategy / Physical AI investment roadmap and demand creation",
        "https://www5.cao.go.jp/keizai-shimon/kaigi/minutes/2026/0721_shiryo03.pdf",
    ),
)


class PhysicalAIPolicyLeadTimeError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PhysicalAIPolicyLeadTimeError(f"{path} must contain a JSON object")
    return payload


def _theme_entry(theme_config: Mapping[str, Any], theme_id: str) -> dict[str, Any]:
    matches = [row for row in theme_config.get("themes") or [] if str(row.get("id")) == theme_id]
    if len(matches) != 1:
        raise PhysicalAIPolicyLeadTimeError(f"theme config must contain exactly one {theme_id}")
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
    limitations.update({"RETROSPECTIVE_MEMBERSHIP", "THEME_SCOPE_PROXY", "BENCHMARK_PROXY"})

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


def build_physical_ai_policy_lead_time_v2(
    *, history: list[dict[str, Any]], theme_config: Mapping[str, Any], theme_id: str = DEFAULT_THEME_ID
) -> dict[str, Any]:
    entry = _theme_entry(theme_config, theme_id)
    members = [dict(member) for member in entry.get("members") or []]
    expected_codes = {"6954", "6506", "6324", "6268", "6481"}
    if {str(member.get("security_code")) for member in members} != expected_codes:
        raise PhysicalAIPolicyLeadTimeError("Physical AI canonical membership does not match Issue #394 PR1 Authority")

    base_limitations = [str(value).upper() for value in (entry.get("limitations") or [])]
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
        "limitations": sorted(set(base_limitations + ["RETROSPECTIVE_MEMBERSHIP", "THEME_SCOPE_PROXY", "BENCHMARK_PROXY"])),
        "policy_checkpoints": checkpoints,
        "policy_evidence_in_market_score": False,
        "source_refs": {
            "membership": "Issue #394 PR1",
            "policy_watchlist": "Issue #154",
            "money_flow_history": DEFAULT_HISTORY,
            "theme_config": DEFAULT_THEME_CONFIG,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Physical AI Policy Lead-Time v2 artifact")
    parser.add_argument("--history", default=DEFAULT_HISTORY)
    parser.add_argument("--theme-config", default=DEFAULT_THEME_CONFIG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_physical_ai_policy_lead_time_v2(
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
