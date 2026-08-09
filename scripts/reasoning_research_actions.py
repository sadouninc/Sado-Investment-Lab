#!/usr/bin/env python3
"""Guided prompts and bounded research actions for Issue #271 PR2."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from reasoning_coverage import SECTION_ORDER, project_reasoning_coverage

GUIDED_PROMPTS = {
    "why_candidate": "この銘柄を今日見る理由は『会社が良いから』以外に、何が変わったからですか？",
    "business_driver": "将来利益を動かす主要ドライバーは何で、まだ確認できていない点は何ですか？",
    "base_scenario": "Base利益が会社予想より上または下なら、その差を作る主な1〜3要因は何ですか？",
    "bear_bull_range": "Baseから外れるなら、最初に動きそうなKPIや条件は何ですか？",
    "valuation": "現在の株価・利益前提は、同じ基準日と単位で比較できる状態ですか？",
    "hypothesis": "市場がまだ十分織り込んでいないと思うことは何ですか？",
    "invalidation": "何が確認されたら『自分の見方を維持しない』と言えますか？",
    "market_expectation": "市場期待を取得できない場合でも、何を事実として比較できるか整理できますか？",
    "next_evidence": "次回決算まで毎日見る必要がありますか？ それとも確認すべきイベントやKPIを限定できますか？",
}

ACTION_BY_SECTION_STATUS = {
    "why_candidate": {"PARTIAL": "CLARIFY_CANDIDATE_CHANGE", "UNKNOWN": "CHECK_CANDIDATE_REASON"},
    "business_driver": {"PARTIAL": "CHECK_EARNINGS_DRIVER", "UNKNOWN": "IDENTIFY_EARNINGS_DRIVER"},
    "base_scenario": {"PARTIAL": "CHECK_EARNINGS_DRIVER", "OWNER_ASSUMPTION": "VALIDATE_OWNER_ASSUMPTION", "UNKNOWN": "DEFINE_BASE_SCENARIO"},
    "bear_bull_range": {"PARTIAL": "CHECK_SCENARIO_DRIVERS", "UNKNOWN": "DEFINE_BEAR_BULL_RANGE"},
    "valuation": {"PARTIAL": "CHECK_VALUATION_BASIS", "STALE": "REFRESH_PRICE_BASIS", "UNKNOWN": "ACQUIRE_VALUATION_BASIS"},
    "hypothesis": {"PARTIAL": "REFINE_HYPOTHESIS", "NOT_YET_DEFINED": "DEFINE_HYPOTHESIS", "CONFLICTING": "RESOLVE_HYPOTHESIS_CONFLICT"},
    "invalidation": {"PARTIAL": "REFINE_INVALIDATION", "NOT_YET_DEFINED": "DEFINE_INVALIDATION"},
    "market_expectation": {"PARTIAL": "CHECK_MARKET_EXPECTATION", "UNAVAILABLE": "REVIEW_WITHOUT_CONSENSUS", "UNKNOWN": "ACQUIRE_CONSENSUS"},
    "next_evidence": {"PARTIAL": "REFINE_NEXT_EVIDENCE", "UNKNOWN": "DEFINE_NEXT_EVIDENCE"},
}

PRIORITY = {
    "CONFLICTING": 0,
    "NOT_YET_DEFINED": 1,
    "STALE": 2,
    "UNKNOWN": 3,
    "UNAVAILABLE": 4,
    "PARTIAL": 5,
    "OWNER_ASSUMPTION": 6,
}

TRADE_TOKENS = {"BUY", "SELL", "ADD", "REDUCE", "DO_NOT_TRADE"}


def build_guided_research_plan(record: dict[str, Any], *, max_actions: int = 3) -> dict[str, Any]:
    """Return Japanese prompts plus at most ``max_actions`` explicit research actions.

    The PR1 projection is consumed read-only. Missing/partial reasoning remains a research
    state: it is never converted into a trade recommendation or trade prohibition.
    """
    if isinstance(max_actions, bool) or not isinstance(max_actions, int) or not 1 <= max_actions <= 3:
        raise ValueError("max_actions must be an integer from 1 to 3")
    original = deepcopy(record)
    coverage = project_reasoning_coverage(record)
    if record != original:
        raise AssertionError("PR1 projection must not mutate input")

    prompts = [
        {"section": section, "prompt_ja": GUIDED_PROMPTS[section]}
        for section in SECTION_ORDER
    ]
    candidates: list[dict[str, Any]] = []
    for order, section in enumerate(SECTION_ORDER):
        status = coverage["sections"][section]["status"]
        action = ACTION_BY_SECTION_STATUS.get(section, {}).get(status)
        if action is None:
            continue
        if action in TRADE_TOKENS:
            raise AssertionError("research action mapping must never emit trade semantics")
        candidates.append(
            {
                "section": section,
                "status": status,
                "action": action,
                "prompt_ja": GUIDED_PROMPTS[section],
                "reason": f"{section} is {status}",
                "_rank": (PRIORITY.get(status, 99), order, action),
            }
        )
    candidates.sort(key=lambda row: row["_rank"])
    actions = []
    seen = set()
    for candidate in candidates:
        key = candidate["action"]
        if key in seen:
            continue
        seen.add(key)
        candidate = {k: v for k, v in candidate.items() if k != "_rank"}
        actions.append(candidate)
        if len(actions) == max_actions:
            break

    return {
        "schema_version": 1,
        "security_code": coverage["security_code"],
        "as_of": coverage["as_of"],
        "coverage_overall": coverage["overall"],
        "guided_prompts": prompts,
        "next_research_actions": actions,
        "semantics": {
            "partial_does_not_prohibit_trade": True,
            "well_supported_is_not_buy_signal": True,
            "trade_recommendation": None,
        },
    }
