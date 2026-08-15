from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PromotionDecision:
    eligible: bool
    reason: str


def evaluate_promotion(
    *,
    issue_number: int,
    source_run_success: bool,
    harness_outcome: str | None,
    source_base_sha: str | None,
    current_base_sha: str | None,
    changed_paths: Iterable[str] | None,
    allowed_paths: Iterable[str] | None,
    forbidden_paths: Iterable[str] | None,
    duplicate_pr_exists: bool = False,
    already_applied: bool = False,
) -> PromotionDecision:
    if issue_number == 79:
        return PromotionDecision(False, "PROTECTED_ISSUE_79")
    if not source_run_success:
        return PromotionDecision(False, "SOURCE_RUN_NOT_SUCCESS")
    if harness_outcome != "REVIEW_READY_VALIDATED":
        return PromotionDecision(False, "SOURCE_NOT_REVIEW_READY_VALIDATED")
    if not source_base_sha or not current_base_sha:
        return PromotionDecision(False, "MALFORMED_METADATA")
    if source_base_sha != current_base_sha:
        return PromotionDecision(False, "BASE_SHA_MISMATCH")
    if duplicate_pr_exists:
        return PromotionDecision(False, "PR_ALREADY_EXISTS")
    if already_applied:
        return PromotionDecision(False, "ALREADY_APPLIED")

    # Fail-closed: reject if any element is blank/whitespace before filtering
    if changed_paths and any(not p or not p.strip() for p in changed_paths):
        return PromotionDecision(False, "ISSUE_CONTRACT_INVALID")
    
    changed = [p for p in (changed_paths or []) if p]
    allowed = [p for p in (allowed_paths or []) if p]
    forbidden = [p for p in (forbidden_paths or []) if p]
    if not changed or not allowed:
        return PromotionDecision(False, "ISSUE_CONTRACT_INVALID")

    for path in changed:
        if not any(fnmatch(path, pattern) for pattern in allowed):
            return PromotionDecision(False, "OUTSIDE_ALLOWED_PATHS")
        if any(fnmatch(path, pattern) for pattern in forbidden):
            return PromotionDecision(False, "FORBIDDEN_PATH")

    return PromotionDecision(True, "ELIGIBLE")


def acceptance_test_argv(command: str) -> list[str]:
    """Parse a validated Work Contract test without invoking a shell.

    Promotion currently supports only pytest-style acceptance commands. Keeping
    this allowlist narrow prevents Issue text from becoming a shell-execution
    surface while still replaying the same acceptance tests used by Gate C.
    """
    argv = shlex.split(command)
    allowed_prefixes = (
        ["python", "-m", "pytest"],
        ["python3", "-m", "pytest"],
        ["pytest"],
    )
    if not argv or not any(argv[: len(prefix)] == prefix for prefix in allowed_prefixes):
        raise ValueError(f"UNSUPPORTED_ACCEPTANCE_TEST:{command}")
    return argv


def run_acceptance_tests(diagnostic_path: Path) -> None:
    payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    contract = payload.get("contract") or {}
    tests = contract.get("acceptance_tests")
    if not isinstance(tests, list) or not tests:
        raise RuntimeError("ISSUE_CONTRACT_INVALID")
    for command in tests:
        argv = acceptance_test_argv(str(command))
        completed = subprocess.run(argv, check=False)
        if completed.returncode != 0:
            raise RuntimeError("POST_APPLY_TEST_FAILED")


def _read_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected true/false")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    decide = subparsers.add_parser("decide")
    decide.add_argument("--issue-number", type=int, required=True)
    decide.add_argument("--source-run-success", type=_bool, required=True)
    decide.add_argument("--harness-outcome", required=True)
    decide.add_argument("--source-base-sha", required=True)
    decide.add_argument("--current-base-sha", required=True)
    decide.add_argument("--changed-paths-file", type=Path, required=True)
    decide.add_argument("--allowed-paths-file", type=Path, required=True)
    decide.add_argument("--forbidden-paths-file", type=Path, required=True)
    decide.add_argument("--duplicate-pr-exists", type=_bool, required=True)
    decide.add_argument("--already-applied", type=_bool, required=True)

    replay = subparsers.add_parser("run-acceptance-tests")
    replay.add_argument("--diagnostic", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "run-acceptance-tests":
        run_acceptance_tests(args.diagnostic)
        return 0

    decision = evaluate_promotion(
        issue_number=args.issue_number,
        source_run_success=args.source_run_success,
        harness_outcome=args.harness_outcome,
        source_base_sha=args.source_base_sha,
        current_base_sha=args.current_base_sha,
        changed_paths=_read_lines(args.changed_paths_file),
        allowed_paths=_read_lines(args.allowed_paths_file),
        forbidden_paths=_read_lines(args.forbidden_paths_file),
        duplicate_pr_exists=args.duplicate_pr_exists,
        already_applied=args.already_applied,
    )
    print(decision.reason)
    return 0 if decision.eligible else 78


if __name__ == "__main__":
    raise SystemExit(main())
