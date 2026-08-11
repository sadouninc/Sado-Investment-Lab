from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .base import ProviderResult


@dataclass
class SectorRotationProvider:
    """Read the latest persisted TOPIX-17 Sector Money Flow set for Morning.

    This adapter is read-only. It does not rerun the detector, recalculate scores,
    mix Theme history into Sector rotation, or convert missing values to zero.
    """

    path: Path = Path("data/generated/public/money-flow/sector-history.jsonl")
    expected_count: int = 17
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
                row = json.loads(line)
                if isinstance(row, dict) and row.get("kind") == "SECTOR":
                    rows.append(row)
        except (OSError, json.JSONDecodeError) as exc:
            return ProviderResult.unavailable(
                self.name,
                reason=f"failed to read Sector Money Flow history: {exc}",
                source_reference=str(self.path),
            )

        dated = [row for row in rows if isinstance(row.get("as_of"), str) and row.get("as_of")]
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
        for row in latest:
            entity_id = str(row.get("id") or "").strip()
            if not entity_id or entity_id in seen:
                continue
            seen.add(entity_id)
            scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
            normalized.append(
                {
                    "id": entity_id,
                    "name": row.get("name"),
                    "state": row.get("state"),
                    "previous_state": row.get("previous_state"),
                    "state_since": row.get("state_since"),
                    "flow_score": row.get("flow_score"),
                    "scores": {
                        "relative_strength": scores.get("relative_strength"),
                        "activity": scores.get("activity"),
                        "breadth": scores.get("breadth"),
                        "heat": scores.get("heat"),
                        "acceleration": scores.get("acceleration"),
                    },
                    "data_completeness": row.get("data_completeness"),
                    "evidence": list(row.get("evidence") or []),
                }
            )

        normalized.sort(key=lambda row: (str(row.get("name") or ""), row["id"]))
        payload = {
            "as_of": latest_as_of,
            "taxonomy": "TOPIX-17",
            "sectors": normalized,
        }

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

        return ProviderResult.ok(
            self.name,
            payload,
            as_of=latest_as_of,
            source_reference=str(self.path),
        )
