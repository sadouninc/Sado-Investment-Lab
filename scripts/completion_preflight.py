"""Standard completion preflight for GitHub issue close operations.

担当: 🌊ナギ
種別: Implementation

This wrapper turns the pure Owner Acceptance validator into a small, deterministic
command that completion tooling can call before a `completed` close. It never
performs a GitHub mutation itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.owner_acceptance_gate import evaluate_close_preflight


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable completion decision for one issue payload."""
    issue_body = payload.get("issue_body", "")
    comments = payload.get("owner_comments", [])
    contract_ambiguous = bool(payload.get("contract_ambiguous", False))

    normalized_comments: list[tuple[str, str]] = []
    for item in comments:
        if not isinstance(item, dict):
            raise ValueError("owner_comments entries must be objects")
        ref = item.get("ref")
        body = item.get("body")
        if not isinstance(ref, str) or not isinstance(body, str):
            raise ValueError("owner_comments entries require string ref/body")
        normalized_comments.append((ref, body))

    result = evaluate_close_preflight(
        issue_body if isinstance(issue_body, str) else "",
        normalized_comments,
        contract_ambiguous=contract_ambiguous,
    )
    return {
        "owner_gate_required": result.owner_gate_required,
        "status": result.status.value,
        "close_allowed": result.close_allowed,
        "evidence_ref": result.evidence_ref,
        "reason": result.reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate Owner Acceptance before closing an issue as completed."
    )
    parser.add_argument("payload", type=Path, help="JSON payload file")
    args = parser.parse_args()

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    result = evaluate_payload(payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["close_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
