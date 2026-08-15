from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.work_contract_validator import validate_issue_body


def evaluate_issue(issue: Mapping[str, Any]) -> dict[str, Any]:
    if "pull_request" in issue:
        return _blocked(("INPUT_IS_PULL_REQUEST",))
    if issue.get("state") != "open":
        return _blocked(("ISSUE_NOT_OPEN",))

    validation = validate_issue_body(issue.get("body") or "")
    if not validation.executable:
        return _blocked(validation.errors, validation.contract)

    return {
        "status": "ELIGIBLE",
        "executable": True,
        "reason_codes": [],
        "contract": validation.contract,
    }


def _blocked(
    reason_codes: tuple[str, ...], contract: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "executable": False,
        "reason_codes": list(reason_codes),
        "contract": contract,
    }


def write_outputs(
    issue: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    diagnostic_output: Path,
    contract_output: Path,
    allowed_paths_output: Path,
    forbidden_paths_output: Path,
) -> None:
    diagnostic_output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not result["executable"]:
        # Remove any pre-existing worker input files to prevent stale artifacts
        contract_output.unlink(missing_ok=True)
        allowed_paths_output.unlink(missing_ok=True)
        forbidden_paths_output.unlink(missing_ok=True)
        return

    body = issue.get("body") or ""
    title = issue.get("title") or ""
    state = issue.get("state") or ""
    number = issue.get("number")
    contract_output.write_text(
        f"# Issue #{number}: {title}\n\nState: {state}\n\n{body}\n", encoding="utf-8"
    )
    contract = result["contract"]
    allowed_paths_output.write_text(
        "\n".join(str(path) for path in contract["allowed_paths"]), encoding="utf-8"
    )
    forbidden_paths_output.write_text(
        "\n".join(str(path) for path in contract["forbidden_paths"]), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-json", type=Path, required=True)
    parser.add_argument("--diagnostic-output", type=Path, required=True)
    parser.add_argument("--contract-output", type=Path, required=True)
    parser.add_argument("--allowed-paths-output", type=Path, required=True)
    parser.add_argument("--forbidden-paths-output", type=Path, required=True)
    args = parser.parse_args()

    issue = json.loads(args.issue_json.read_text(encoding="utf-8"))
    result = evaluate_issue(issue)
    write_outputs(
        issue,
        result,
        diagnostic_output=args.diagnostic_output,
        contract_output=args.contract_output,
        allowed_paths_output=args.allowed_paths_output,
        forbidden_paths_output=args.forbidden_paths_output,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["executable"] else 78


if __name__ == "__main__":
    raise SystemExit(main())
