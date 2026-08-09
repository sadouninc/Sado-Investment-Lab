from copy import deepcopy

import pytest

from scripts.opportunity_cost_adapters import (
    OpportunityCostAdapterError,
    build_opportunity_set_from_decision,
    opportunity_set_snapshot_source,
)


def _decision(**overrides):
    value = {
        "security_code": "6622",
        "decided_at": "2026-08-09T10:30:00+09:00",
        "decision": "BUY",
        "actor": "SADO",
        "confidence": "MEDIUM",
        "owner_judgment": {
            "why_now": "決算後の前提を確認した",
            "biggest_risk": "需要減速",
            "what_changes_my_mind": "受注減少",
        },
        "system_snapshot": {},
        "evidence_refs": [],
    }
    value.update(overrides)
    return value


def _selector(**overrides):
    value = {
        "ref": "candidate-selector:2026-08-09T10:00+09:00",
        "captured_at": "2026-08-09T10:00:00+09:00",
        "data": {
            "as_of": "2026-08-09",
            "ranked_candidates": [
                {
                    "security_code": "6622",
                    "company_name": "ダイヘン",
                    "selection_reason": "change_signal 90 — 決算変化",
                    "research_status": "CURRENT",
                },
                {
                    "security_code": "5803",
                    "company_name": "フジクラ",
                    "selection_reason": "theme_relevance 85 — AI電力需要",
                    "research_status": "STALE",
                    "research_ref": "research:5803:v1",
                },
                {
                    "security_code": "5016",
                    "company_name": "JX金属",
                    "selection_reason": "investment_relevance 80 — 保有候補",
                    "research_status": "NOT_STARTED",
                },
            ],
        },
    }
    value.update(overrides)
    return value


def test_builds_ex_ante_ranked_alternatives_and_cash():
    result = build_opportunity_set_from_decision(_decision(), selector_snapshot=_selector(), top_n=2)
    by_code = {item.get("security_code"): item for item in result["alternatives"]}
    assert "6622" not in by_code
    assert by_code["5803"]["rank_at_decision"] == 2
    assert by_code["5803"]["data_status"] == "STALE"
    assert by_code["5803"]["candidate_ref"].endswith("#rank:2:security:5803")
    assert by_code["5016"]["rank_at_decision"] == 3
    assert by_code["5016"]["data_status"] == "MISSING"
    assert by_code[None]["action"] == "CASH"


def test_candidate_rank_is_not_recomputed_from_priority():
    selector = _selector()
    selector["data"]["ranked_candidates"][1]["total_priority"] = 1
    selector["data"]["ranked_candidates"][2]["total_priority"] = 99
    result = build_opportunity_set_from_decision(_decision(), selector_snapshot=selector, top_n=2)
    ranks = {item.get("security_code"): item.get("rank_at_decision") for item in result["alternatives"]}
    assert ranks["5803"] == 2
    assert ranks["5016"] == 3


def test_future_selector_snapshot_is_rejected():
    selector = _selector(captured_at="2026-08-09T10:31:00+09:00")
    with pytest.raises(OpportunityCostAdapterError, match="must not be later"):
        build_opportunity_set_from_decision(_decision(), selector_snapshot=selector)


def test_owner_named_alternative_is_explicit_and_not_ranked():
    result = build_opportunity_set_from_decision(
        _decision(),
        selector_snapshot=_selector(),
        top_n=0,
        include_cash=False,
        owner_named_alternatives=[
            {
                "security_code": "4063",
                "action": "BUY",
                "why_feasible": "Ownerが比較対象として明示",
                "why_not_chosen": "決算前で不確実",
                "data_status": "UNKNOWN",
            }
        ],
    )
    item = result["alternatives"][0]
    assert item["source"] == "OWNER_NAMED"
    assert item["security_code"] == "4063"
    assert "rank_at_decision" not in item


def test_duplicate_candidate_and_owner_identity_fails_closed():
    with pytest.raises(ValueError, match="duplicate alternatives"):
        build_opportunity_set_from_decision(
            _decision(),
            selector_snapshot=_selector(),
            top_n=1,
            include_cash=False,
            owner_named_alternatives=[
                {
                    "security_code": "5803",
                    "action": "BUY",
                    "why_feasible": "Owner明示",
                    "data_status": "CURRENT",
                }
            ],
        )


def test_missing_selection_reason_fails_closed():
    selector = _selector()
    selector["data"]["ranked_candidates"][1]["selection_reason"] = ""
    with pytest.raises(OpportunityCostAdapterError, match="selection_reason"):
        build_opportunity_set_from_decision(_decision(), selector_snapshot=selector, top_n=1)


def test_in_progress_research_remains_unknown():
    selector = _selector()
    selector["data"]["ranked_candidates"][1]["research_status"] = "IN_PROGRESS"
    result = build_opportunity_set_from_decision(_decision(), selector_snapshot=selector, top_n=1)
    item = next(item for item in result["alternatives"] if item.get("security_code") == "5803")
    assert item["data_status"] == "UNKNOWN"


def test_unsupported_decision_type_is_not_inferred():
    with pytest.raises(OpportunityCostAdapterError, match="outside #186 PR2 scope"):
        build_opportunity_set_from_decision(
            _decision(decision="START_RESEARCH"), selector_snapshot=_selector()
        )


def test_selector_input_is_not_mutated():
    selector = _selector()
    original = deepcopy(selector)
    build_opportunity_set_from_decision(_decision(), selector_snapshot=selector)
    assert selector == original


def test_deterministic_same_input_same_opportunity_set():
    left = build_opportunity_set_from_decision(_decision(), selector_snapshot=_selector())
    right = build_opportunity_set_from_decision(_decision(), selector_snapshot=_selector())
    assert left == right
    assert left["opportunity_set_id"] == right["opportunity_set_id"]


def test_snapshot_source_links_to_decision_snapshot_adapter_shape():
    opportunity = build_opportunity_set_from_decision(_decision(), selector_snapshot=_selector())
    source = opportunity_set_snapshot_source(opportunity)
    assert source["ref"] == opportunity["opportunity_set_id"]
    assert source["captured_at"] == opportunity["captured_at"]
    assert source["data"]["opportunity_set_id"] == opportunity["opportunity_set_id"]


def test_top_n_zero_without_other_alternative_is_rejected():
    with pytest.raises(OpportunityCostAdapterError, match="at least one ex-ante alternative"):
        build_opportunity_set_from_decision(
            _decision(), selector_snapshot=_selector(), top_n=0, include_cash=False
        )
