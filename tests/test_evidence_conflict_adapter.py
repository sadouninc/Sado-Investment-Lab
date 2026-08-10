import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evidence_conflict import detect_conflict
from evidence_conflict_adapter import project_reasoning_conflict_detail, project_research_debt_candidate


def _claims():
    base = {
        "kind": "KPI", "metric": "orders", "fiscal_period": "FY2026Q2",
        "unit": "JPY_MN", "basis": "company", "definition": "v1", "as_of": "2026-08-10",
    }
    return [
        {**base, "claim_ref": "c1", "evidence_ref": "e1", "value": 100},
        {**base, "claim_ref": "c2", "evidence_ref": "e2", "value": 120},
    ]


def test_reasoning_projection_is_read_only_conflicting_detail():
    conflict = detect_conflict("6622", _claims())
    before = copy.deepcopy(conflict)
    detail = project_reasoning_conflict_detail(conflict)
    assert detail["status"] == "CONFLICTING"
    assert detail["conflict_type"] == "VALUE_MISMATCH"
    assert detail["claim_refs"] == ["c1", "c2"]
    assert detail["trade_recommendation"] is None
    assert conflict == before


def test_material_unresolved_conflict_becomes_debt_candidate():
    conflict = detect_conflict("6622", _claims())
    debt = project_research_debt_candidate(conflict, materiality="HIGH", created_at="2026-08-10")
    assert debt["origin_type"] == "CONFLICTING"
    assert debt["origin_ref"] == conflict["conflict_id"]
    assert debt["section"] == "hypothesis"
    assert debt["trade_recommendation"] is None


def test_materiality_is_never_inferred_and_low_does_not_promote():
    conflict = detect_conflict("6622", _claims())
    assert project_research_debt_candidate(conflict, materiality=None, created_at="2026-08-10") is None
    assert project_research_debt_candidate(conflict, materiality="LOW", created_at="2026-08-10") is None


def test_resolved_conflict_does_not_create_debt():
    conflict = detect_conflict("6622", _claims())
    conflict["status"] = "RESOLVED"
    conflict["resolution_ref"] = "resolution:1"
    assert project_research_debt_candidate(conflict, materiality="HIGH", created_at="2026-08-10") is None


def test_owner_interpretation_requirement_is_preserved_not_selected():
    claims = _claims()
    for claim in claims:
        claim["kind"] = "INTERPRETATION"
    conflict = detect_conflict("6622", claims)
    detail = project_reasoning_conflict_detail(conflict)
    assert detail["resolution_requirement"] == ["OWNER_INTERPRETATION_REQUIRED"]
    assert detail["resolution_ref"] is None
