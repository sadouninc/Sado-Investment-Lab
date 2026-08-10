from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONCEPT_PATH = Path(__file__).with_name("concept-v1.json")
OS_MAP_PATH = Path(__file__).with_name("os-map-v1.json")
OUTPUT_PATH = ROOT / "site-src" / "concepts" / "investment-decision-cockpit" / "index.md"

REQUIRED = {
    "feature_id", "route_ref", "os_stage_ref", "purpose_ja", "first_checks",
    "why_it_matters", "common_states", "next_destination_refs", "evidence_refs",
    "non_goals", "contract_refs", "last_reviewed_at",
}
FAIL_CLOSED_STATES = {"UNKNOWN", "UNAVAILABLE", "STALE"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def route_inventory(os_map: dict) -> set[str]:
    routes = {entry["route"] for entry in os_map.get("today_entries", []) if entry.get("route")}
    routes |= {stage["primary_destination"] for stage in os_map.get("stages", []) if stage.get("primary_destination")}
    return routes


def validate_concept(record: dict, os_map: dict) -> None:
    missing = REQUIRED - record.keys()
    if missing:
        raise ValueError(f"missing required fields: {sorted(missing)}")
    if not 1 <= len(record["first_checks"]) <= 3:
        raise ValueError("first_checks must contain 1..3 items")
    stages = {stage["stage_id"] for stage in os_map["stages"]}
    if record["os_stage_ref"] not in stages:
        raise ValueError("unknown os_stage_ref")
    routes = route_inventory(os_map)
    for ref in [record["route_ref"], *record["next_destination_refs"], *record["evidence_refs"]]:
        if ref not in routes:
            raise ValueError(f"unknown route/evidence ref: {ref}")
    states = {item["status"]: item["meaning_ja"] for item in record["common_states"]}
    if set(states) != FAIL_CLOSED_STATES:
        raise ValueError("UNKNOWN / UNAVAILABLE / STALE meanings are required")
    if any(not text.strip() for text in states.values()):
        raise ValueError("state meanings must be explicit")


def render(record: dict, os_map: dict) -> str:
    before = copy.deepcopy(record)
    validate_concept(record, os_map)
    checks = "\n".join(f"{i}. {text}" for i, text in enumerate(record["first_checks"], 1))
    states = "\n".join(f"- **{item['status']}** — {item['meaning_ja']}" for item in record["common_states"])
    next_links = "\n".join(f"- [{ref}]({{{{ '{ref}' | relative_url }}}})" for ref in record["next_destination_refs"])
    evidence = "\n".join(f"- [{ref}]({{{{ '{ref}' | relative_url }}}})" for ref in record["evidence_refs"])
    non_goals = "\n".join(f"- {text}" for text in record["non_goals"])
    flow = " → ".join(record["decision_flow_ja"])
    output = f'''---
layout: site
title: Investment Decision Cockpit — 見方ガイド
permalink: /concepts/investment-decision-cockpit/
---

# Investment Decision Cockpit — 見方ガイド

## この機能は何のため？
{record['purpose_ja']}

## 最初に見る3点
{checks}

## なぜ見る？
{record['why_it_matters']}

### 判断の流れ
`{flow}`

## 状態の意味
{states}

## 次に進む
{next_links}

## 根拠を見る
{evidence}

<details class="sil-disclosure">
<summary>この機能がしないこと</summary>
<div class="sil-disclosure__body">
{non_goals}
</div>
</details>

> 最終確認: {record['last_reviewed_at']} / Contract: {' / '.join(record['contract_refs'])}
'''
    if record != before:
        raise AssertionError("Concept rendering mutated canonical input")
    return output


def main() -> None:
    data = load_json(CONCEPT_PATH)
    os_map = load_json(OS_MAP_PATH)
    record = data["concepts"][0]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render(record, os_map), encoding="utf-8")


if __name__ == "__main__":
    main()
