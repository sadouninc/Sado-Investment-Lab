from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from evidence_conflict import EvidenceConflictError, detect_conflict


def claim(ref, value=100, **changes):
    row = {
        "claim_ref": ref, "evidence_ref": f"evidence:{ref}", "kind": "KPI",
        "metric": "revenue", "fiscal_period": "FY2026", "unit": "JPY_MN",
        "basis": "consolidated", "definition": "revenue-v1", "value": value,
        "as_of": "2026-08-09T12:00:00+09:00",
    }
    row.update(changes)
    return row


def test_value_mismatch_only_after_alignment():
    result = detect_conflict("6622", [claim("a", 100), claim("b", 120)])
    assert result["conflict_type"] == "VALUE_MISMATCH"
    assert result["trade_recommendation"] is None


def test_period_mismatch_prevents_value_comparison():
    result = detect_conflict("6622", [claim("a", 100), claim("b", 120, fiscal_period="FY2027")])
    assert result["conflict_type"] == "PERIOD_MISMATCH"
    assert result["resolution_requirement"] == ["ALIGN_FISCAL_PERIOD"]


def test_unit_mismatch_fails_closed_without_conversion():
    result = detect_conflict("6622", [claim("a", 100), claim("b", 100_000_000, unit="JPY")])
    assert result["conflict_type"] == "UNKNOWN"
    assert result["resolution_requirement"] == ["ALIGN_UNIT"]


def test_basis_and_definition_are_classified_before_value():
    assert detect_conflict("6622", [claim("a"), claim("b", basis="segment")])["conflict_type"] == "BASIS_MISMATCH"
    assert detect_conflict("6622", [claim("a"), claim("b", definition="revenue-v2")])["conflict_type"] == "DEFINITION_CHANGE"


def test_interpretation_requires_owner_and_newer_does_not_win():
    old = claim("a", "demand strong", kind="INTERPRETATION", as_of="2026-08-01T00:00:00+09:00")
    new = claim("b", "demand weak", kind="INTERPRETATION", as_of="2026-08-09T00:00:00+09:00")
    result = detect_conflict("6622", [old, new])
    assert result["conflict_type"] == "INTERPRETATION_DIVERGENCE"
    assert result["resolution_requirement"] == ["OWNER_INTERPRETATION_REQUIRED"]
    assert len(result["claims"]) == 2


def test_deterministic_order_independent_and_non_mutating():
    source = [claim("b", 120), claim("a", 100)]
    before = deepcopy(source)
    first = detect_conflict("6622", source)
    second = detect_conflict("6622", list(reversed(source)))
    assert first == second
    assert source == before


def test_requires_two_complete_claims():
    with pytest.raises(EvidenceConflictError):
        detect_conflict("6622", [claim("a")])
    broken = claim("b")
    del broken["unit"]
    with pytest.raises(EvidenceConflictError):
        detect_conflict("6622", [claim("a"), broken])
