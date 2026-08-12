from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def recovery_decision(
    *, as_of: str, report_path: Path, diagnostic_path: Path
) -> dict[str, str]:
    """Return a deterministic, fail-closed decision for a Morning rerun."""
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError("as_of must be an ISO date") from exc

    if not report_path.is_file():
        return {"action": "RUN", "reason": "REPORT_MISSING"}

    diagnostic = _load_json(diagnostic_path)
    if diagnostic is None:
        return {"action": "RUN", "reason": "DIAGNOSTIC_MISSING_OR_INVALID"}
    if diagnostic.get("status") != "OK":
        return {"action": "RUN", "reason": "DIAGNOSTIC_NOT_OK"}
    if diagnostic.get("dataset_as_of") != as_of:
        return {"action": "RUN", "reason": "DATASET_DATE_MISMATCH"}
    if diagnostic.get("report_path") not in (None, str(report_path).replace("\\", "/")):
        return {"action": "RUN", "reason": "REPORT_PATH_MISMATCH"}
    return {"action": "NOOP", "reason": "TODAY_ALREADY_GENERATED"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard idempotent AI Morning recovery runs")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--report")
    parser.add_argument("--diagnostic")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    report = Path(args.report or f"05_Daily_Reports/Morning/{args.as_of}.md")
    diagnostic = Path(
        args.diagnostic or f"data/generated/diagnostics/openai/{args.as_of}.json"
    )
    decision = recovery_decision(
        as_of=args.as_of, report_path=report, diagnostic_path=diagnostic
    )
    should_generate = "true" if decision["action"] == "RUN" else "false"
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as output:
            output.write(f"should_generate={should_generate}\n")
            output.write(f"reason={decision['reason']}\n")
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
