"""Read-only, deterministic GitHub Actions failure analysis for Issue #873.

This module deliberately does not call GitHub or publish issues. A separate,
permission-scoped workflow will be responsible for discovery and mutation.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from typing import Any

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_RULES = (
    ("DEPENDENCY_SETUP_FAILURE", ("setup python", "setup node", "install dependencies", "pip install", "npm ci"), "依存関係・環境セットアップの失敗を確認する"),
    ("TEST_FAILURE", ("pytest", "unittest", "test", "unit test"), "失敗したテストのログと直近の変更を確認する"),
    ("BUILD_FAILURE", ("build", "compile", "lint", "typecheck"), "ビルドまたは静的検査の失敗ログを確認する"),
)


def _safe_text(value: Any, limit: int = 120) -> str:
    """Treat GitHub-provided labels as untrusted display-only text."""
    return re.sub(r"[<>\r\n\t`|]", " ", str(value or "")).strip()[:limit]


def _positive_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise ValueError("identifier must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("identifier must be a positive integer") from exc
    if number < 1:
        raise ValueError("identifier must be a positive integer")
    return number


def analyze_completed_failure(
    repository: str,
    workflow_run: Mapping[str, Any],
    jobs: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Analyze one actual completed, failed run. Never synthesize failures."""
    if not _REPOSITORY.fullmatch(repository):
        raise ValueError("invalid repository")
    if workflow_run.get("status") != "completed" or workflow_run.get("conclusion") != "failure":
        return None
    run_id = _positive_int(workflow_run.get("id"))
    failed = [j for j in jobs if j.get("conclusion") == "failure"]
    if not failed:
        return None  # Incomplete job inventory must not become invented evidence.
    job = min(failed, key=lambda j: _positive_int(j.get("id")))
    job_id = _positive_int(job.get("id"))
    failing_steps = [s for s in (job.get("steps") or []) if s.get("conclusion") == "failure"]
    step = failing_steps[0] if failing_steps else None
    step_name = _safe_text(step.get("name", "") if step else "")
    error_class = "UNCLASSIFIED_JOB_FAILURE"
    next_fix = "失敗ジョブのログを取得し、根因を確認する"
    for category, names, recommendation in _RULES:
        if any(token in step_name.lower() for token in names):
            error_class, next_fix = category, recommendation
            break
    digest = hashlib.sha256(f"{repository}:{run_id}:{error_class}".encode("utf-8")).hexdigest()[:20]
    return {
        "source_run_id": run_id,
        "job_id": job_id,
        "workflow_name": _safe_text(workflow_run.get("name")),
        "error_class": error_class,
        "first_seen_at": str(workflow_run.get("created_at") or ""),
        "affected_component": _safe_text(job.get("name")),
        "failing_step": step_name,
        "candidate_root_cause": f"HYPOTHESIS: {error_class}（実際のログによる根因検証は未完了）",
        "reproduction_evidence": f"https://github.com/{repository}/actions/runs/{run_id}/job/{job_id}",
        "next_minimal_fix": next_fix,
        "request_id": f"actions-failure-{digest}",
        "evidence_status": "OBSERVED_FAILURE_ROOT_CAUSE_UNVERIFIED",
    }


def decide_issue_action(
    analysis: Mapping[str, Any] | None,
    existing_issues: Iterable[Mapping[str, Any]],
    *,
    inventory_complete: bool,
) -> str:
    """Fail closed if an issue inventory is incomplete or a duplicate exists."""
    if analysis is None:
        return "NO_FAILURE"
    if not inventory_complete:
        return "HOLD_INCOMPLETE_ISSUE_INVENTORY"
    marker = f"<!-- {analysis['request_id']} -->"
    for issue in existing_issues:
        if issue.get("number") == 79:
            continue  # Never inspect or mutate the protected issue as a target.
        if marker in str(issue.get("body") or ""):
            return "DUPLICATE_SUPPRESSED"
    return "ISSUE_DRAFT_ELIGIBLE"


def build_issue_draft(analysis: Mapping[str, Any]) -> dict[str, str]:
    """Produce a draft only; never apply READY labels or perform a mutation."""
    error_class = _safe_text(analysis["error_class"])
    request_id = str(analysis["request_id"])
    if not re.fullmatch(r"actions-failure-[0-9a-f]{20}", request_id):
        raise ValueError("invalid request identifier")
    marker = f"<!-- {request_id} -->"
    title = f"[Actions障害] {error_class} / run {_positive_int(analysis['source_run_id'])}"
    body = "\n".join((
        "担当: 🌙ルナ（解析） / 実装Owner未確定",
        "種別: GitHub Actions障害 / 要トリアージ",
        marker,
        f"- 実行証跡: {_safe_text(analysis['reproduction_evidence'], 300)}",
        f"- workflow: {_safe_text(analysis['workflow_name'])}",
        f"- job_id: {_positive_int(analysis['job_id'])}",
        f"- failure step: {_safe_text(analysis['failing_step']) or 'UNKNOWN'}",
        f"- 分類: {error_class}",
        f"- 原因候補: {_safe_text(analysis['candidate_root_cause'], 240)}",
        f"- 最小の次アクション: {_safe_text(analysis['next_minimal_fix'], 240)}",
        "- Acceptance Criteria: 実ログで根因を特定し、修正PRのCI成功を確認する。",
        "- 状態: TRIAGE_REQUIRED。READY_FOR_IMPLEMENTATIONには自動昇格しない。",
        "- 安全: #79変更禁止。権限・秘密情報・有料・破壊的操作はOwner判断待ち。",
    ))
    return {"title": title, "body": body}
