#!/usr/bin/env python3
"""Deterministic fail-closed guard for the Jules scheduled dispatcher.

The guard intentionally does not execute Jules itself. It validates the Owner-controlled
Issue #685 control record and emits a small machine-readable decision for the workflow.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass


ALLOWED_READY_STATES = {"READY_FOR_SCHEDULED_RUN"}
STOP_STATES = {"STOP", "PAUSE", "HOLD", "NO-OP"}
FORBIDDEN_ISSUE = 79


@dataclass(frozen=True)
class DispatchControl:
    state: str
    run_token: str | None
    target_issue: int | None


def _section_value(body: str, heading: str) -> str | None:
    """Read the first value below an exact level-2 heading, tolerating whitespace/CRLF only."""
    pattern = rf"^##[ \t]+{re.escape(heading)}[ \t]*\r?\n[ \t]*([^\r\n]+)"
    match = re.search(pattern, body, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_control(body: str) -> DispatchControl:
    state = (_section_value(body, "STATE") or "").strip()
    token_match = re.search(r"ACTIVE RUN TOKEN:\s*`([^`]+)`", body)
    target_match = re.search(r"TARGET:\s*#(\d+)\b", body)
    return DispatchControl(
        state=state,
        run_token=token_match.group(1) if token_match else None,
        target_issue=int(target_match.group(1)) if target_match else None,
    )


def decide(
    control: DispatchControl,
    *,
    secret_present: bool,
    target_open: bool,
    target_ready: bool,
    overlapping_pr: bool,
    last_consumed_run_token: str | None = None,
) -> str:
    if control.state in STOP_STATES:
        return "STOP_NOOP"
    if control.state not in ALLOWED_READY_STATES:
        return "SYNC_UNVERIFIED_NOOP"
    if not control.run_token or control.target_issue is None:
        return "NO_TASK_NOOP"
    if control.target_issue == FORBIDDEN_ISSUE:
        return "FORBIDDEN_TARGET_NOOP"
    if last_consumed_run_token and control.run_token == last_consumed_run_token:
        return "STALE_RUN_TOKEN_NOOP"
    if not secret_present:
        return "MISSING_SECRET_NOOP"
    if not target_open or not target_ready:
        return "DUPLICATE_TARGET_NOOP"
    if overlapping_pr:
        return "PATH_CONFLICT_NOOP"
    return "DISPATCH_ALLOWED"


def build_prompt(control_body: str, target_body: str) -> str:
    """Return a bounded prompt sourced only from Owner-controlled GitHub SSoT."""
    return (
        "You are the Jules implementation executor for Sado Investment Lab.\n"
        "GitHub is the SSoT. Execute exactly one task and never substitute another.\n"
        "Before changing files, repeat the duplicate/path/owner-conflict preflight on fresh main.\n"
        "If already satisfied or conflicting, make no changes and terminate NO-OP.\n"
        "Never modify Issue #79. Never merge. Open a PR only for a non-empty diff.\n\n"
        "=== Jules Control Issue #685 ===\n"
        f"{control_body}\n\n"
        "=== Target Issue ===\n"
        f"{target_body}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-json", required=True)
    parser.add_argument("--target-json", required=True)
    parser.add_argument("--secret-present", choices=("true", "false"), required=True)
    parser.add_argument("--overlapping-pr", choices=("true", "false"), default="false")
    parser.add_argument("--last-consumed-run-token")
    args = parser.parse_args()

    with open(args.control_json, encoding="utf-8") as fh:
        control_json = json.load(fh)
    with open(args.target_json, encoding="utf-8") as fh:
        target_json = json.load(fh)

    control_body = control_json.get("body") or ""
    target_body = target_json.get("body") or ""
    control = parse_control(control_body)
    target_ready = "READY_FOR_IMPLEMENTATION" in target_body or "READY_FOR_IMPLEMENTATION" in json.dumps(
        target_json.get("comments", []), ensure_ascii=False
    )

    result = decide(
        control,
        secret_present=args.secret_present == "true",
        target_open=target_json.get("state") == "open",
        target_ready=target_ready,
        overlapping_pr=args.overlapping_pr == "true",
        last_consumed_run_token=args.last_consumed_run_token,
    )

    output = {
        "result": result,
        "run_token": control.run_token,
        "target_issue": control.target_issue,
    }
    if result == "DISPATCH_ALLOWED":
        output["prompt"] = build_prompt(control_body, target_body)
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
