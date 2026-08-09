from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping


class ResearchQueueError(ValueError):
    """Raised when a research queue transition violates the contract."""


QUEUE_STATUSES = {"QUEUED", "IN_PROGRESS", "CURRENT", "NEEDS_REVIEW"}


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ResearchQueueError(f"{field} is required")
    return text


def _normalize_sources(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ResearchQueueError("candidate_sources must be a non-empty array")
    result = tuple(sorted({_required_text(item, "candidate_source") for item in value}))
    return result


@dataclass(frozen=True)
class ResearchQueueRecord:
    security_code: str
    company_name: str
    candidate_sources: tuple[str, ...]
    selection_reason: str
    owner_pick: bool
    candidate_as_of: str
    research_status: str | None = None
    research_gap: str | None = None
    money_flow_context: Mapping[str, Any] | None = None
    status: str = "QUEUED"

    @classmethod
    def from_candidate_handoff(cls, raw: Mapping[str, Any]) -> "ResearchQueueRecord":
        status = str(raw.get("status", "QUEUED")).upper()
        if status != "QUEUED":
            raise ResearchQueueError("candidate handoff must enter as QUEUED")
        return cls(
            security_code=_required_text(raw.get("security_code"), "security_code"),
            company_name=_required_text(raw.get("company_name"), "company_name"),
            candidate_sources=_normalize_sources(raw.get("candidate_sources")),
            selection_reason=_required_text(raw.get("selection_reason"), "selection_reason"),
            owner_pick=bool(raw.get("owner_pick", False)),
            candidate_as_of=_required_text(raw.get("candidate_as_of"), "candidate_as_of"),
            research_status=(str(raw["research_status"]) if raw.get("research_status") is not None else None),
            research_gap=(str(raw["research_gap"]) if raw.get("research_gap") is not None else None),
            money_flow_context=raw.get("money_flow_context"),
            status="QUEUED",
        )

    @property
    def identity(self) -> str:
        return f"company-research:{self.security_code}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "security_code": self.security_code,
            "company_name": self.company_name,
            "candidate_sources": list(self.candidate_sources),
            "selection_reason": self.selection_reason,
            "owner_pick": self.owner_pick,
            "candidate_as_of": self.candidate_as_of,
            "research_status": self.research_status,
            "research_gap": self.research_gap,
            "money_flow_context": self.money_flow_context,
            "status": self.status,
        }


def start_research(record: ResearchQueueRecord, *, command: str) -> ResearchQueueRecord:
    """Move QUEUED to IN_PROGRESS only through explicit START_RESEARCH."""
    if command != "START_RESEARCH":
        raise ResearchQueueError("explicit START_RESEARCH command is required")
    if record.status == "IN_PROGRESS":
        return record
    if record.status != "QUEUED":
        raise ResearchQueueError(f"cannot START_RESEARCH from {record.status}")
    return replace(record, status="IN_PROGRESS")


def complete_research(record: ResearchQueueRecord, *, quality_gate_passed: bool) -> ResearchQueueRecord:
    if record.status not in {"IN_PROGRESS", "NEEDS_REVIEW"}:
        raise ResearchQueueError(f"cannot complete research from {record.status}")
    next_status = "CURRENT" if quality_gate_passed else "NEEDS_REVIEW"
    if record.status == next_status:
        return record
    return replace(record, status=next_status)


class ResearchQueueRegistry:
    """Small idempotent registry keyed only by canonical security_code identity."""

    def __init__(self) -> None:
        self._records: dict[str, ResearchQueueRecord] = {}

    def enqueue(self, record: ResearchQueueRecord) -> str:
        existing = self._records.get(record.security_code)
        if existing is None:
            self._records[record.security_code] = record
            return "INSERTED"
        if existing == record:
            return "UNCHANGED"
        raise ResearchQueueError(
            f"conflicting queue payload for security_code={record.security_code}; silent overwrite forbidden"
        )

    def get(self, security_code: str) -> ResearchQueueRecord | None:
        return self._records.get(str(security_code))
