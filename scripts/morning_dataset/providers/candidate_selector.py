from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from .base import ProviderResult


@dataclass
class CandidateSelectorProvider:
    """Read the existing #108 Candidate Selector output for Morning Dataset.

    This provider is read-only. It does not rank, infer, or invent candidates;
    those responsibilities remain with the Candidate Selector pipeline.
    """

    path: Path = Path("data/generated/public/candidate-selector.json")
    limit: int = 10
    max_age_days: int = 3
    today: date | None = None
    name: str = "candidates"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical Candidate Selector snapshot not found",
                source_reference=str(self.path),
            )
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read Candidate Selector snapshot: {exc}",
                source_reference=str(self.path),
            )
        if not isinstance(raw, dict):
            return ProviderResult.unavailable(
                self.name,
                reason="Candidate Selector snapshot must be a JSON object",
                source_reference=str(self.path),
            )

        as_of = self._as_of(raw.get("as_of"))
        ranked = raw.get("ranked_candidates")
        if not isinstance(ranked, list):
            ranked = raw.get("candidates")
        if not isinstance(ranked, list):
            return ProviderResult.unavailable(
                self.name,
                reason="Candidate Selector snapshot has no candidate list",
                source_reference=str(self.path),
            )

        eligible: list[dict[str, Any]] = []
        unresolved = 0
        for row in ranked:
            if not isinstance(row, dict):
                continue
            code = row.get("security_code")
            name = row.get("company_name")
            if not isinstance(code, str) or not code.strip() or not isinstance(name, str) or not name.strip():
                unresolved += 1
                continue
            eligible.append(
                {
                    "security_code": code.strip(),
                    "company_name": name.strip(),
                    "rank": len(eligible) + 1,
                    "status": row.get("research_status") or "UNKNOWN",
                    "total_priority": row.get("total_priority"),
                    "owner_pick": bool(row.get("owner_pick")),
                    "candidate_sources": list(row.get("candidate_sources") or []),
                    "selection_reason": row.get("selection_reason"),
                    "last_researched_at": row.get("last_researched_at"),
                }
            )
            if len(eligible) >= self.limit:
                break

        if not eligible:
            return ProviderResult.unavailable(
                self.name,
                status="MISSING",
                as_of=as_of,
                source_reference=str(self.path),
                reason="Candidate Selector has no security-code-resolved candidates for Morning",
            )
        if as_of is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                source_reference=str(self.path),
                reason="Candidate Selector candidates are usable but snapshot as_of is missing or invalid",
                data=eligible,
            )

        age_days = ((self.today or date.today()) - datetime.strptime(as_of, "%Y-%m-%d").date()).days
        if age_days > self.max_age_days:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=as_of,
                source_reference=str(self.path),
                reason=f"Candidate Selector snapshot is {age_days} days old (freshness limit {self.max_age_days})",
                data=eligible,
            )

        # Unresolved Candidate Selector records are deliberately excluded from the
        # Morning security shortlist rather than assigned guessed codes. Their
        # existence is not a freshness/completeness defect in the eligible feed.
        return ProviderResult.ok(
            self.name,
            eligible,
            as_of=as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _as_of(value: object) -> str | None:
        if not isinstance(value, str) or len(value) < 10:
            return None
        candidate = value[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
        except ValueError:
            return None
        return candidate
