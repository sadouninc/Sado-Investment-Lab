from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import math
from pathlib import Path
from typing import Any

from .base import ProviderResult
from scripts.japan_market_calendar import is_japan_market_business_day

_MAX_INT_DIGITS = 64
_MAX_JSON_DEPTH = 100


def _bounded_int(text: str) -> int:
    if len(text.lstrip("+-")) > _MAX_INT_DIGITS:
        raise ValueError("integer literal exceeds the supported size")
    return int(text)


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite number literal")
    return value


def _reject_constant(_value: str) -> float:
    raise ValueError("non-standard JSON constant")


def _previous_market_business_day(report_date: date) -> date:
    candidate = report_date - timedelta(days=1)
    while not is_japan_market_business_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


@dataclass
class SectorRotationProvider:
    """Read the latest persisted TOPIX-17 Sector Money Flow set for Morning.

    This adapter is read-only. It does not rerun the detector, recalculate scores,
    mix Theme history into Sector rotation, or convert missing values to zero.
    """

    path: Path = Path("data/generated/public/money-flow/sector-history.jsonl")
    expected_count: int = 17
    report_date: date | None = None
    name: str = "sector_rotation"

    def collect(self) -> ProviderResult:
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="canonical Sector Money Flow history not found",
                source_reference=str(self.path),
            )

        rows: list[dict[str, Any]] = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(
                    line,
                    parse_int=_bounded_int,
                    parse_float=_finite_float,
                    parse_constant=_reject_constant,
                )
                if isinstance(row, dict) and row.get("kind") == "SECTOR":
                    rows.append(row)
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read Sector Money Flow history: {exc.__class__.__name__}",
                source_reference=str(self.path),
            )

        dated = []
        invalid_date_rows = 0
        for row in rows:
            as_of_value = row.get("as_of")
            if not isinstance(as_of_value, str) or not as_of_value:
                invalid_date_rows += 1
                continue
            try:
                date.fromisoformat(as_of_value)
            except ValueError:
                invalid_date_rows += 1
                continue
            dated.append(row)
        if not dated:
            return ProviderResult.unavailable(
                self.name,
                reason="Sector Money Flow history has no dated SECTOR snapshots",
                source_reference=str(self.path),
            )

        latest_as_of = max(str(row["as_of"]) for row in dated)
        latest = [row for row in dated if str(row["as_of"]) == latest_as_of]

        seen: set[str] = set()
        normalized: list[dict[str, Any]] = []
        integrity_issues = invalid_date_rows
        for row in latest:
            entity_id_value = row.get("id")
            if not isinstance(entity_id_value, str) or not entity_id_value.strip():
                integrity_issues += 1
                continue
            entity_id = entity_id_value.strip()
            if entity_id in seen:
                integrity_issues += 1
                continue
            seen.add(entity_id)
            scores_value = row.get("scores")
            if scores_value is None:
                scores = {}
            elif isinstance(scores_value, dict):
                scores = scores_value
            else:
                scores = {}
                integrity_issues += 1
            evidence_value = row.get("evidence")
            if evidence_value is None:
                evidence = []
            elif isinstance(evidence_value, list):
                if self._is_safe_json_value(evidence_value):
                    evidence = evidence_value
                else:
                    evidence = []
                    integrity_issues += 1
            else:
                evidence = []
                integrity_issues += 1

            flow_score, valid = self._finite_number_or_none(row.get("flow_score"))
            integrity_issues += int(not valid)
            normalized_scores: dict[str, int | float | None] = {}
            for key in ("relative_strength", "activity", "breadth", "heat", "acceleration"):
                normalized_scores[key], valid = self._finite_number_or_none(scores.get(key))
                integrity_issues += int(not valid)
            text_fields = {}
            for key in ("name", "state", "previous_state", "state_since", "data_completeness"):
                value = row.get(key)
                if value is None or isinstance(value, str):
                    text_fields[key] = value
                else:
                    text_fields[key] = None
                    integrity_issues += 1
            normalized.append(
                {
                    "id": entity_id,
                    "name": text_fields["name"],
                    "state": text_fields["state"],
                    "previous_state": text_fields["previous_state"],
                    "state_since": text_fields["state_since"],
                    "flow_score": flow_score,
                    "scores": normalized_scores,
                    "data_completeness": text_fields["data_completeness"],
                    "evidence": evidence,
                }
            )

        normalized.sort(key=lambda row: (str(row.get("name") or ""), row["id"]))
        payload = {
            "as_of": latest_as_of,
            "taxonomy": "TOPIX-17",
            "sectors": normalized,
        }

        if self.report_date is None:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason="Morning report date is required to verify Sector snapshot freshness",
                data=payload,
            )

        if integrity_issues:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason=f"latest Sector set contains {integrity_issues} input integrity issue(s)",
                data=payload,
            )

        try:
            actual_as_of = date.fromisoformat(latest_as_of)
        except ValueError:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason=f"invalid Sector snapshot as_of: actual={latest_as_of}",
                data=payload,
            )

        try:
            expected_as_of = _previous_market_business_day(self.report_date)
        except (OverflowError, ValueError) as exc:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason=f"unable to determine expected Sector snapshot for report_date={self.report_date.isoformat()}: {exc}",
                data=payload,
            )

        if len(normalized) != self.expected_count:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason=f"latest canonical Sector set contains {len(normalized)} / {self.expected_count} sectors",
                data=payload,
            )

        if any(row.get("data_completeness") != "OK" for row in normalized):
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason="latest Sector set contains non-OK canonical snapshots",
                data=payload,
            )

        if actual_as_of < expected_as_of:
            return ProviderResult.unavailable(
                self.name,
                status="STALE",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason=(
                    "Sector snapshot is older than the Morning freshness contract: "
                    f"actual={latest_as_of}, expected={expected_as_of.isoformat()}"
                ),
                data=payload,
            )

        if actual_as_of > expected_as_of:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                as_of=latest_as_of,
                source_reference=str(self.path),
                reason=(
                    "Sector snapshot is newer than the confirmed Morning cutoff: "
                    f"actual={latest_as_of}, expected={expected_as_of.isoformat()}"
                ),
                data=payload,
            )

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=latest_as_of,
            source_reference=str(self.path),
        )

    @staticmethod
    def _finite_number_or_none(value: Any) -> tuple[int | float | None, bool]:
        if value is None:
            return None, True
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, False
        if isinstance(value, float) and not math.isfinite(value):
            return None, False
        return value, True

    @staticmethod
    def _is_safe_json_value(value: Any) -> bool:
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > _MAX_JSON_DEPTH:
                return False
            if item is None or isinstance(item, (str, bool, int)):
                continue
            if isinstance(item, float):
                if not math.isfinite(item):
                    return False
                continue
            if isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
                continue
            if isinstance(item, dict):
                if not all(isinstance(key, str) for key in item):
                    return False
                pending.extend((child, depth + 1) for child in item.values())
                continue
            return False
        return True


