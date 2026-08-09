from __future__ import annotations

import copy
from typing import Any, Mapping

from scripts.company_research import CompanyResearchRecord
from scripts.research_revision_ledger import (
    ResearchRevisionError,
    numeric_delta,
    validate_revision,
)


class ResearchRevisionAdapterError(ValueError):
    """Raised when two canonical Company Research artifacts cannot be revised safely."""


SCENARIO_NAMES = ("bear", "base", "bull")
SCENARIO_FIELDS = (
    "eps",
    "net_income",
    "share_basis",
    "assumptions",
    "source_type",
    "source_refs",
    "as_of",
)


def _scenario(record: CompanyResearchRecord, name: str) -> Mapping[str, Any]:
    value = record.scenarios.get(name)
    if not isinstance(value, Mapping):
        raise ResearchRevisionAdapterError(f"scenarios.{name} must be an object")
    return value


def _target_fiscal_years(record: CompanyResearchRecord) -> set[str]:
    years: set[str] = set()
    for name in SCENARIO_NAMES:
        scenario = _scenario(record, name)
        year = scenario.get("target_fiscal_year")
        if year:
            years.add(str(year))
    return years


def _change_type(before_exists: bool, after_exists: bool) -> str:
    if not before_exists:
        return "ADDED"
    if not after_exists:
        return "REMOVED"
    return "UPDATED"


def _field_change(
    *,
    path: str,
    before_scenario: Mapping[str, Any],
    after_scenario: Mapping[str, Any],
    field: str,
    target_fiscal_year: str,
) -> dict[str, Any] | None:
    before_exists = field in before_scenario
    after_exists = field in after_scenario
    before_value = copy.deepcopy(before_scenario.get(field))
    after_value = copy.deepcopy(after_scenario.get(field))
    if before_exists == after_exists and before_value == after_value:
        return None

    change: dict[str, Any] = {
        "path": f"{path}.{field}",
        "before": before_value,
        "after": after_value,
        "change_type": _change_type(before_exists, after_exists),
        "target_fiscal_year": target_fiscal_year,
    }
    delta = numeric_delta(before_value, after_value)
    if delta["absolute"] is not None:
        change["numeric_delta"] = delta
    return change


def build_scenario_revision_candidate(
    before_raw: Mapping[str, Any],
    after_raw: Mapping[str, Any],
    *,
    revised_at: str,
    trigger_type: str,
    trigger_ref: str | None,
    reasoning: str,
    evidence_refs: list[str],
    materiality: str,
    author_type: str,
    previous_revision_ref: str | None = None,
) -> dict[str, Any] | None:
    """Create one append-ready #183 SCENARIO revision from canonical Research before/after.

    The adapter never mutates the canonical artifact. If scenarios did not actually change,
    None is returned so event passage alone cannot create a fabricated revision.
    """
    before = CompanyResearchRecord.from_mapping(before_raw)
    after = CompanyResearchRecord.from_mapping(after_raw)
    if before.security_code != after.security_code:
        raise ResearchRevisionAdapterError("security_code mismatch")

    before_years = _target_fiscal_years(before)
    after_years = _target_fiscal_years(after)
    if len(before_years) != 1 or len(after_years) != 1:
        raise ResearchRevisionAdapterError("all available Bear/Base/Bull scenarios must use one target fiscal year")
    before_year = next(iter(before_years))
    after_year = next(iter(after_years))
    if before_year != after_year:
        raise ResearchRevisionAdapterError(
            "FY mismatch: do not encode a fiscal-year rollover as a scenario revision delta"
        )

    changes: list[dict[str, Any]] = []
    for name in SCENARIO_NAMES:
        before_scenario = _scenario(before, name)
        after_scenario = _scenario(after, name)
        before_scenario_year = before_scenario.get("target_fiscal_year")
        after_scenario_year = after_scenario.get("target_fiscal_year")
        if before_scenario_year != after_scenario_year:
            raise ResearchRevisionAdapterError(f"scenarios.{name}.target_fiscal_year mismatch")
        for field in SCENARIO_FIELDS:
            change = _field_change(
                path=f"scenarios.{name}",
                before_scenario=before_scenario,
                after_scenario=after_scenario,
                field=field,
                target_fiscal_year=before_year,
            )
            if change is not None:
                if field in {"eps", "net_income"}:
                    change["source_type_before"] = before_scenario.get("source_type", "SADO_SCENARIO")
                    change["source_type_after"] = after_scenario.get("source_type", "SADO_SCENARIO")
                    change["share_basis_before"] = copy.deepcopy(before_scenario.get("share_basis"))
                    change["share_basis_after"] = copy.deepcopy(after_scenario.get("share_basis"))
                changes.append(change)

    if not changes:
        return None
    if not str(reasoning or "").strip():
        raise ResearchRevisionAdapterError("reasoning is required when scenario values changed")
    if not isinstance(evidence_refs, list):
        raise ResearchRevisionAdapterError("evidence_refs must be an array")

    changed_scenarios = sorted({change["path"].split(".")[1] for change in changes})
    revision = {
        "entity_type": "COMPANY",
        "entity_id": after.security_code,
        "artifact_type": "SCENARIO",
        "artifact_ref": f"research:{after.security_code}:scenarios:{after_year}",
        "revised_at": revised_at,
        "trigger_type": trigger_type,
        "trigger_ref": trigger_ref,
        "previous_revision_ref": previous_revision_ref,
        "change_summary": " / ".join(name.capitalize() for name in changed_scenarios) + " シナリオを更新",
        "changed_fields": changes,
        "reasoning": reasoning,
        "evidence_refs": list(evidence_refs),
        "confidence_before": before.hypothesis.get("current_confidence"),
        "confidence_after": after.hypothesis.get("current_confidence"),
        "materiality": materiality,
        "author_type": author_type,
        "as_of": after.as_of,
        "target_fiscal_year": after_year,
        "scenario_source_types": {
            name: _scenario(after, name).get("source_type", "SADO_SCENARIO")
            for name in SCENARIO_NAMES
        },
    }
    try:
        return validate_revision(revision)
    except ResearchRevisionError as exc:
        raise ResearchRevisionAdapterError(str(exc)) from exc
