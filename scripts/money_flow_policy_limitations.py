from __future__ import annotations

from datetime import date
from typing import Any


RETROSPECTIVE_POLICY = "RETROSPECTIVE_MEMBERSHIP_IF_HISTORICAL_MEMBERSHIP_UNAVAILABLE"


def has_retrospective_membership_history(
    history: list[dict[str, Any]], *, theme_config: dict[str, Any], theme_id: str
) -> bool:
    """Return True when persisted history necessarily used current membership retrospectively.

    This derives the limitation from canonical history + explicit theme configuration instead of
    the wall-clock date of the latest scheduled run, so a later refresh cannot erase a limitation
    introduced by historical backfill.
    """
    matches = [row for row in theme_config.get("themes") or [] if str(row.get("id")) == theme_id]
    if len(matches) != 1:
        raise ValueError(f"theme config must contain exactly one {theme_id}")
    entry = matches[0]
    if str(entry.get("backfill_policy") or "") != RETROSPECTIVE_POLICY:
        return False
    membership_as_of = date.fromisoformat(str(entry["membership_as_of"]))
    return any(
        row.get("kind") == "THEME"
        and str(row.get("id")) == theme_id
        and date.fromisoformat(str(row["as_of"])) < membership_as_of
        for row in history
    )
