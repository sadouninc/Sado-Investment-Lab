from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Iterable, Mapping


AMAZON_Q_LABEL = "Amazon Q development agent"
JULES_CONTROL_ISSUE = 685
FORBIDDEN_ISSUE = 79
SUPPORTED_EXECUTORS = {"AMAZON_Q", "JULES", "SORA"}


@dataclass(frozen=True)
class DispatchPlan:
    executor: str
    target_issue: int
    lease_id: str
    action: str
    idempotency_key: str
    evidence_marker: str
    payload: Mapping[str, Any]


def _target_issue(work_ref: Any) -> int:
    match = re.fullmatch(r"#([1-9][0-9]*)", str(work_ref).strip())
    if not match:
        raise ValueError("work_ref must be canonical #<issue_number>")
    issue = int(match.group(1))
    if issue == FORBIDDEN_ISSUE:
        raise ValueError("Issue #79 is hard-denied")
    return issue


def _validated_lease(lease: Mapping[str, Any]) -> tuple[str, str, int]:
    lease_id = str(lease.get("lease_id", "")).strip()
    executor = str(lease.get("executor", "")).strip().upper()
    if not lease_id:
        raise ValueError("lease_id is required")
    if executor not in SUPPORTED_EXECUTORS:
        raise ValueError("unsupported executor")
    target_issue = _target_issue(lease.get("work_ref"))
    return lease_id, executor, target_issue


def evidence_marker(*, lease_id: str, executor: str, target_issue: int) -> str:
    return (
        "<!-- AUTO_ROUTER_DISPATCH "
        f"lease_id={lease_id} executor={executor} target_issue={target_issue} -->"
    )


def already_dispatched(comments: Iterable[Mapping[str, Any]], *, lease_id: str) -> bool:
    needle = f"lease_id={lease_id} "
    for comment in comments:
        if needle in str(comment.get("body", "")) and "AUTO_ROUTER_DISPATCH" in str(
            comment.get("body", "")
        ):
            return True
    return False


def build_dispatch_plan(lease: Mapping[str, Any]) -> DispatchPlan:
    """Build one idempotent provider-specific dispatch plan without side effects."""
    lease_id, executor, target_issue = _validated_lease(lease)
    marker = evidence_marker(
        lease_id=lease_id, executor=executor, target_issue=target_issue
    )
    key_material = f"{lease_id}|{executor}|{target_issue}"
    idempotency_key = sha256(key_material.encode("utf-8")).hexdigest()[:24]

    if executor == "AMAZON_Q":
        action = "ADD_ISSUE_LABEL"
        payload: Mapping[str, Any] = {
            "issue_number": target_issue,
            "label": AMAZON_Q_LABEL,
            "evidence_comment": marker,
        }
    elif executor == "JULES":
        action = "ARM_JULES_CONTROL"
        payload = {
            "control_issue": JULES_CONTROL_ISSUE,
            "target_issue": target_issue,
            "state": "READY_FOR_SCHEDULED_RUN",
            "run_token": f"auto-router-{lease_id}",
            "evidence_comment": marker,
        }
    else:
        action = "PERSIST_SORA_LEASE"
        payload = {
            "issue_number": target_issue,
            "state": "DISPATCHED",
            "evidence_comment": marker,
        }

    return DispatchPlan(
        executor=executor,
        target_issue=target_issue,
        lease_id=lease_id,
        action=action,
        idempotency_key=idempotency_key,
        evidence_marker=marker,
        payload=payload,
    )
