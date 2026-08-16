#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.operational_state_guard import (
    evaluate_auto_green_merge,
    mode_contract,
    should_activate_delegated_sora_sm,
)

UNKNOWN = None

DELEGATION_FIXTURES: tuple[dict[str, Any], ...] = (
    {"mode": "AWAY", "trigger": "QUEUE_STARVATION", "expected": True},
    {"mode": "AWAY", "trigger": "OWNER_CONFLICT", "expected": True},
    {"mode": "AWAY", "trigger": "NO_REROUTE_AFTER_BLOCKED_ESCAPE", "expected": True},
    {"mode": "AWAY", "trigger": "ORDINARY_IMPLEMENTATION", "expected": False},
    {"mode": "ACTIVE_AUTO", "trigger": "QUEUE_STARVATION", "expected": False},
)

AUTO_GREEN_BASE = {
    "mode": "ACTIVE_AUTO",
    "ci_pass": True,
    "request_changes": False,
    "merge_conflict": False,
    "required_gates_pass": True,
    "latest_head_reviewed": True,
    "owner_or_investment_authority": False,
    "sensitive_change": False,
    "explicit_owner_acceptance_required": False,
    "protected_issue_79": False,
}

AUTO_GREEN_FIXTURES: tuple[dict[str, Any], ...] = (
    {"name": "low-risk-green", "expected": "ELIGIBLE", "overrides": {}},
    {"name": "required-gate-missing", "expected": "BLOCK", "overrides": {"required_gates_pass": False}},
    {"name": "ci-failure", "expected": "BLOCK", "overrides": {"ci_pass": False}},
    {
        "name": "owner-acceptance-required",
        "expected": "BLOCK",
        "overrides": {"explicit_owner_acceptance_required": True},
    },
    {"name": "sensitive-change", "expected": "BLOCK", "overrides": {"sensitive_change": True}},
    {
        "name": "latest-head-review-unknown",
        "expected": "BLOCK",
        "overrides": {"latest_head_reviewed": False},
    },
)


def parse_team_state(text: str) -> dict[str, str | None]:
    """Extract explicit current mode fields from TEAM_STATE without inference."""
    result: dict[str, str | None] = {"user_mode": UNKNOWN, "merge_policy": UNKNOWN}
    for key in result:
        match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([A-Z_]+)\s*$", text)
        if match:
            result[key] = match.group(1)
    return result


def evaluate_delegation_fixtures(
    fixtures: Sequence[Mapping[str, Any]] = DELEGATION_FIXTURES,
) -> dict[str, Any]:
    activations = 0
    mismatches: list[str] = []
    for index, fixture in enumerate(fixtures):
        actual = should_activate_delegated_sora_sm(
            mode=str(fixture["mode"]), trigger=str(fixture["trigger"])
        )
        expected = fixture.get("expected")
        if not isinstance(expected, bool):
            return {
                "delegated_flow_activation_count": UNKNOWN,
                "delegated_flow_steps": UNKNOWN,
                "delegation_fixture_mismatches": [f"fixture:{index}:missing_expected"],
            }
        activations += int(actual)
        if actual != expected:
            mismatches.append(f"fixture:{index}:{fixture['trigger']}")
    return {
        "delegated_flow_activation_count": activations,
        "delegated_flow_steps": UNKNOWN,
        "delegation_fixture_mismatches": mismatches,
    }


def evaluate_auto_green_fixtures(
    fixtures: Sequence[Mapping[str, Any]] = AUTO_GREEN_FIXTURES,
) -> dict[str, Any]:
    evaluated = 0
    eligible = 0
    blocked = 0
    dangerous_false_positive = 0
    mismatches: list[str] = []

    for index, fixture in enumerate(fixtures):
        expected = fixture.get("expected")
        if expected not in {"ELIGIBLE", "BLOCK"}:
            return {
                "shadow_auto_green_evaluated_count": UNKNOWN,
                "shadow_auto_green_eligible_count": UNKNOWN,
                "shadow_auto_green_blocked_count": UNKNOWN,
                "dangerous_false_positive_count": UNKNOWN,
                "shadow_fixture_mismatches": [f"fixture:{index}:missing_expected"],
            }
        values = dict(AUTO_GREEN_BASE)
        overrides = fixture.get("overrides")
        if not isinstance(overrides, Mapping):
            overrides = {}
        values.update(overrides)
        result = evaluate_auto_green_merge(**values)
        actual = "ELIGIBLE" if result.allowed else "BLOCK"
        evaluated += 1
        eligible += int(result.allowed)
        blocked += int(not result.allowed)
        if expected == "BLOCK" and result.allowed:
            dangerous_false_positive += 1
        if actual != expected:
            mismatches.append(str(fixture.get("name") or f"fixture:{index}"))

    return {
        "shadow_auto_green_evaluated_count": evaluated,
        "shadow_auto_green_eligible_count": eligible,
        "shadow_auto_green_blocked_count": blocked,
        "dangerous_false_positive_count": dangerous_false_positive,
        "shadow_fixture_mismatches": mismatches,
    }


def build_operational_mode_telemetry(
    *,
    team_state_text: str,
    global_scan_steps: int | None = None,
    delegated_flow_steps: int | None = None,
) -> dict[str, Any]:
    state = parse_team_state(team_state_text)
    delegation = evaluate_delegation_fixtures()
    shadow = evaluate_auto_green_fixtures()

    if delegated_flow_steps is not None:
        delegation["delegated_flow_steps"] = delegated_flow_steps

    user_mode = state["user_mode"]
    merge_policy = state["merge_policy"]
    if user_mode is not None and merge_policy is not None:
        contract_policy = mode_contract(user_mode)["merge_policy"]
        if contract_policy != merge_policy:
            merge_policy = UNKNOWN

    metrics = {
        "user_mode": user_mode,
        "merge_policy": merge_policy,
        "delegated_flow_activation_count": delegation["delegated_flow_activation_count"],
        "delegated_flow_steps": delegation["delegated_flow_steps"],
        "global_scan_steps": global_scan_steps,
        "shadow_auto_green_evaluated_count": shadow["shadow_auto_green_evaluated_count"],
        "shadow_auto_green_eligible_count": shadow["shadow_auto_green_eligible_count"],
        "shadow_auto_green_blocked_count": shadow["shadow_auto_green_blocked_count"],
        "dangerous_false_positive_count": shadow["dangerous_false_positive_count"],
    }

    return {
        "schema_version": 1,
        "source": "#625/#627 User Mode v2 shadow evidence",
        "metrics": metrics,
        "evidence": {
            "delegation_fixture_mismatches": delegation["delegation_fixture_mismatches"],
            "shadow_fixture_mismatches": shadow["shadow_fixture_mismatches"],
            "unknown_policy": "missing evidence remains null; it is never coerced to zero",
        },
    }


def main(team_state_path: str, out_path: str | None = None) -> None:
    text = Path(team_state_path).read_text(encoding="utf-8")
    record = build_operational_mode_telemetry(team_state_text=text)
    payload = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if out_path:
        Path(out_path).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    import sys

    if len(sys.argv) not in {2, 3}:
        print("usage: operational_mode_telemetry.py TEAM_STATE.md [OUTPUT_JSON]")
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
