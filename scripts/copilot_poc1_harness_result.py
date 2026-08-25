from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


def parse_copilot_result(content: str | None) -> dict[str, Any]:
    if not content:
        return {
            "outcome": None,
            "changed_files": None,
            "validation": None,
            "blocked_reason": None,
            "confirmation_count": None,
        }

    parsed: dict[str, Any] = {
        "outcome": None,
        "changed_files": None,
        "validation": None,
        "blocked_reason": None,
        "confirmation_count": None,
    }

    lines = content.splitlines()
    for line in lines:
        cleaned = re.sub(r"^\*+|\*+$", "", line.strip()).strip()
        if ":" not in cleaned:
            continue
        key, val = cleaned.split(":", 1)
        key = key.strip().lower()
        val = val.strip()

        if key == "outcome":
            parsed["outcome"] = val if val else None
        elif key == "changed_files":
            if val and val.upper() != "NONE":
                parsed["changed_files"] = [f.strip() for f in val.split(",") if f.strip()]
            else:
                parsed["changed_files"] = []
        elif key == "validation":
            parsed["validation"] = val if val else None
        elif key == "blocked_reason":
            if val and val.upper() != "NONE":
                parsed["blocked_reason"] = val
            else:
                parsed["blocked_reason"] = None
        elif key == "confirmation_count":
            if val.isdigit():
                parsed["confirmation_count"] = int(val)
            else:
                parsed["confirmation_count"] = None

    return parsed


def classify_outcome(
    harness_outcome: str | None,
    contract_preflight_outcome: str | None,
    provider_execution_reached: bool,
    scope_violations: Sequence[str],
) -> str:
    if harness_outcome == "BLOCKED_CONTRACT_PREFLIGHT" or contract_preflight_outcome == "BLOCKED":
        return "CONTROL_PLANE_FAIL"
    if harness_outcome in ("BLOCKED_ISSUE_PATH_CONTRACT", "BLOCKED_FORBIDDEN_PATH") or len(scope_violations) > 0:
        return "SCOPE_FAIL"
    if harness_outcome == "BLOCKED_NO_REPO_DIFF":
        return "NO_OUTPUT"
    if harness_outcome == "REVIEW_READY_VALIDATED":
        return "SUCCESS"
    if harness_outcome in (
        "BLOCKED_RESULT_MISSING",
        "BLOCKED_AGENT_NOT_REVIEW_READY",
        "BLOCKED_BEFORE_HARNESS_COMPLETE",
    ) or not harness_outcome:
        return "HARNESS_ERROR"
    return "HARNESS_ERROR"


def _read_file_lines(path: Path | str | None) -> list[str]:
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_file_text(path: Path | str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8")


def _read_json(path: Path | str | None) -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        pass
    return None


def build_harness_result(
    *,
    issue_number: int | None = None,
    run_id: int | str | None = None,
    run_attempt: int | str | None = None,
    repository: str | None = None,
    harness_outcome: str | None = None,
    contract_preflight_outcome: str | None = None,
    provider_execution_reached: bool | None = None,
    issue_file: Path | str | None = None,
    work_contract_preflight_file: Path | str | None = None,
    allowed_paths_file: Path | str | None = None,
    forbidden_paths_file: Path | str | None = None,
    changed_paths_file: Path | str | None = None,
    scope_violations_file: Path | str | None = None,
    copilot_result_file: Path | str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    # Extract facts or defaults
    if issue_number is None and issue_file:
        issue_data = _read_json(issue_file)
        if issue_data and isinstance(issue_data.get("number"), int):
            issue_number = issue_data["number"]

    preflight_data = _read_json(work_contract_preflight_file)
    if contract_preflight_outcome is None and preflight_data:
        contract_preflight_outcome = preflight_data.get("status")

    allowed_paths = _read_file_lines(allowed_paths_file)
    forbidden_paths = _read_file_lines(forbidden_paths_file)
    changed_files = _read_file_lines(changed_paths_file)
    scope_violations = _read_file_lines(scope_violations_file)

    copilot_raw = _read_file_text(copilot_result_file)
    agent_facts = parse_copilot_result(copilot_raw)

    if provider_execution_reached is None:
        # Provider execution was reached if preflight didn't block before copilot run
        if harness_outcome == "BLOCKED_CONTRACT_PREFLIGHT":
            provider_execution_reached = False
        elif copilot_raw is not None or harness_outcome in (
            "BLOCKED_NO_REPO_DIFF",
            "BLOCKED_FORBIDDEN_PATH",
            "BLOCKED_ISSUE_PATH_CONTRACT",
            "BLOCKED_RESULT_MISSING",
            "BLOCKED_AGENT_NOT_REVIEW_READY",
            "REVIEW_READY_VALIDATED",
        ):
            provider_execution_reached = True
        else:
            provider_execution_reached = False

    workflow_run_url = None
    if repository and run_id:
        workflow_run_url = f"https://github.com/{repository}/actions/runs/{run_id}"

    classification = classify_outcome(
        harness_outcome=harness_outcome,
        contract_preflight_outcome=contract_preflight_outcome,
        provider_execution_reached=provider_execution_reached,
        scope_violations=scope_violations,
    )

    timestamps: dict[str, Any] | None = None
    if start_time or end_time or elapsed_seconds is not None:
        timestamps = {
            "start_time": start_time,
            "end_time": end_time,
            "elapsed_seconds": elapsed_seconds,
        }

    return {
        "schema_version": "1.0",
        "issue_number": issue_number,
        "run_id": str(run_id) if run_id is not None else None,
        "run_attempt": int(run_attempt) if run_attempt is not None and str(run_attempt).isdigit() else None,
        "workflow_run_url": workflow_run_url,
        "harness_outcome": harness_outcome,
        "contract_preflight_outcome": contract_preflight_outcome,
        "provider_execution_reached": provider_execution_reached,
        "changed_files": changed_files,
        "allowed_paths": allowed_paths,
        "forbidden_paths": forbidden_paths,
        "scope_violations": scope_violations,
        "agent_declared_outcome": agent_facts["outcome"],
        "agent_blocked_reason": agent_facts["blocked_reason"],
        "confirmation_count": agent_facts["confirmation_count"],
        "validation_summary": agent_facts["validation"],
        "classification": classification,
        "timestamps": timestamps,
    }


def render_step_summary(result: dict[str, Any]) -> str:
    lines = [
        "### Harness Diagnostic Evidence (v1)",
        f"- **Issue Number**: #{result.get('issue_number') or 'UNKNOWN'}",
        f"- **Harness Outcome**: `{result.get('harness_outcome') or 'UNKNOWN'}`",
        f"- **Classification**: `{result.get('classification')}`",
        f"- **Contract Preflight**: `{result.get('contract_preflight_outcome') or 'UNKNOWN'}`",
        f"- **Provider Execution Reached**: `{result.get('provider_execution_reached')}`",
        f"- **Changed Files Count**: `{len(result.get('changed_files') or [])}`",
    ]

    violations = result.get("scope_violations") or []
    if violations:
        lines.append(f"- **Scope Violations**: `{', '.join(violations)}`")

    blocked_reason = result.get("agent_blocked_reason")
    if blocked_reason:
        lines.append(f"- **Agent Blocked Reason**: `{blocked_reason}`")

    declared_outcome = result.get("agent_declared_outcome")
    if declared_outcome:
        lines.append(f"- **Agent Declared Outcome**: `{declared_outcome}`")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Copilot PoC1 Harness Result JSON and Summary")
    parser.add_argument("--issue-number", type=int, default=None)
    parser.add_argument("--issue-file", type=Path, default=Path("/tmp/issue.json"))
    parser.add_argument("--work-contract-preflight-file", type=Path, default=Path("/tmp/work-contract-preflight.json"))
    parser.add_argument("--allowed-paths-file", type=Path, default=Path("/tmp/issue-allowed-paths.txt"))
    parser.add_argument("--forbidden-paths-file", type=Path, default=Path("/tmp/issue-forbidden-paths.txt"))
    parser.add_argument("--changed-paths-file", type=Path, default=Path("/tmp/changed-paths.txt"))
    parser.add_argument("--scope-violations-file", type=Path, default=Path("/tmp/forbidden-paths.txt"))
    parser.add_argument("--copilot-result-file", type=Path, default=Path("/tmp/copilot-result.md"))
    parser.add_argument("--output-json", type=Path, default=Path("/tmp/harness-result.json"))
    parser.add_argument("--summary-file", type=Path, default=None)

    args = parser.parse_args()

    harness_outcome = os.getenv("HARNESS_OUTCOME")
    contract_preflight_outcome = os.getenv("CONTRACT_PREFLIGHT_OUTCOME")
    run_id = os.getenv("GITHUB_RUN_ID")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT")
    repository = os.getenv("GITHUB_REPOSITORY")

    result = build_harness_result(
        issue_number=args.issue_number,
        run_id=run_id,
        run_attempt=run_attempt,
        repository=repository,
        harness_outcome=harness_outcome,
        contract_preflight_outcome=contract_preflight_outcome,
        issue_file=args.issue_file,
        work_contract_preflight_file=args.work_contract_preflight_file,
        allowed_paths_file=args.allowed_paths_file,
        forbidden_paths_file=args.forbidden_paths_file,
        changed_paths_file=args.changed_paths_file,
        scope_violations_file=args.scope_violations_file,
        copilot_result_file=args.copilot_result_file,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_text = render_step_summary(result)
    summary_path = args.summary_file or (Path(os.getenv("GITHUB_STEP_SUMMARY")) if os.getenv("GITHUB_STEP_SUMMARY") else None)
    if summary_path:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(summary_text)

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
