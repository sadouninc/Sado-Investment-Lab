from copy import deepcopy

import pytest

from scripts.investment_episode import InvestmentEpisodeError, build_investment_episodes


def decision(action, at, suffix):
    return {
        "security_code": "6622",
        "decided_at": at,
        "decision": action,
        "actor": "SADO",
        "confidence": "MEDIUM",
        "owner_judgment": {
            "why_now": f"why-{suffix}",
            "biggest_risk": f"risk-{suffix}",
            "what_changes_my_mind": f"change-{suffix}",
        },
        "system_snapshot": {},
        "evidence_refs": [],
    }


def canonical(state, at, ref="portfolio:1"):
    return {
        "security_code": "6622",
        "as_of": at,
        "source_ref": ref,
        "authority": "CANONICAL",
        "position_state": state,
    }


def test_buy_add_hold_reduce_are_grouped_without_mutating_decisions():
    items = [
        decision("BUY", "2026-08-01T09:00:00+09:00", "buy"),
        decision("ADD", "2026-08-02T09:00:00+09:00", "add"),
        decision("HOLD", "2026-08-03T09:00:00+09:00", "hold"),
        decision("REDUCE", "2026-08-04T09:00:00+09:00", "reduce"),
    ]
    original = deepcopy(items)
    result = build_investment_episodes(items)
    episode = result["episodes"][0]
    assert episode["status"] == "PARTIAL_EXIT"
    assert episode["data_status"] == "COMPLETE"
    assert len(episode["decision_refs"]) == 4
    assert items == original


def test_sell_does_not_close_without_canonical_portfolio_authority():
    result = build_investment_episodes([
        decision("BUY", "2026-08-01T09:00:00+09:00", "buy"),
        decision("SELL", "2026-08-05T09:00:00+09:00", "sell"),
    ])
    episode = result["episodes"][0]
    assert episode["status"] == "UNKNOWN"
    assert episode["closed_at"] is None
    assert episode["exit_decision_ref"] is None
    assert episode["data_status"] == "PARTIAL"


def test_sell_closes_only_with_canonical_not_owned_confirmation():
    result = build_investment_episodes(
        [
            decision("BUY", "2026-08-01T09:00:00+09:00", "buy"),
            decision("SELL", "2026-08-05T09:00:00+09:00", "sell"),
        ],
        portfolio_confirmations=[canonical("NOT_OWNED", "2026-08-05T15:30:00+09:00")],
    )
    episode = result["episodes"][0]
    assert episode["status"] == "CLOSED"
    assert episode["closed_at"] == "2026-08-05T15:30:00+09:00"
    assert episode["portfolio_authority_ref"] == "portfolio:1"
    assert episode["exit_decision_ref"] == episode["decision_refs"][-1]


def test_noncanonical_portfolio_confirmation_is_rejected():
    bad = canonical("NOT_OWNED", "2026-08-05T15:30:00+09:00")
    bad["authority"] = "INFERRED"
    with pytest.raises(InvestmentEpisodeError, match="CANONICAL"):
        build_investment_episodes([decision("BUY", "2026-08-01T09:00:00+09:00", "buy")], portfolio_confirmations=[bad])


def test_rebuy_after_confirmed_close_starts_new_episode():
    result = build_investment_episodes(
        [
            decision("BUY", "2026-08-01T09:00:00+09:00", "buy1"),
            decision("SELL", "2026-08-05T09:00:00+09:00", "sell"),
            decision("BUY", "2026-08-10T09:00:00+09:00", "buy2"),
        ],
        portfolio_confirmations=[canonical("NOT_OWNED", "2026-08-05T15:30:00+09:00")],
    )
    assert len(result["episodes"]) == 2
    assert result["episodes"][0]["status"] == "CLOSED"
    assert result["episodes"][1]["status"] == "OPEN"
    assert result["episodes"][0]["episode_id"] != result["episodes"][1]["episode_id"]


def test_unjournaled_trade_is_a_gap_and_does_not_create_decision():
    result = build_investment_episodes(
        [decision("BUY", "2026-08-01T09:00:00+09:00", "buy")],
        trades=[{
            "trade_ref": "sbi:2026-09-01:1",
            "security_code": "6622",
            "executed_at": "2026-09-01T10:00:00+09:00",
            "action": "ADD",
            "decision_ref": None,
        }],
    )
    assert result["unjournaled_gaps"] == [{
        "type": "UNJOURNALED_GAP",
        "trade_ref": "sbi:2026-09-01:1",
        "security_code": "6622",
        "executed_at": "2026-09-01T10:00:00+09:00",
        "action": "ADD",
        "decision_ref": None,
    }]
    assert len(result["episodes"][0]["decision_refs"]) == 1


def test_explicit_trade_decision_ref_must_exist():
    with pytest.raises(InvestmentEpisodeError, match="not present"):
        build_investment_episodes(
            [decision("BUY", "2026-08-01T09:00:00+09:00", "buy")],
            trades=[{
                "trade_ref": "sbi:x",
                "security_code": "6622",
                "executed_at": "2026-09-01T10:00:00+09:00",
                "action": "ADD",
                "decision_ref": "decision:missing",
            }],
        )


def test_add_without_entry_is_partial_unknown_not_fabricated_buy():
    result = build_investment_episodes([decision("ADD", "2026-08-02T09:00:00+09:00", "add")])
    episode = result["episodes"][0]
    assert episode["status"] == "UNKNOWN"
    assert episode["entry_decision_ref"] is None
    assert episode["data_status"] == "PARTIAL"


def test_allocation_episode_relation_is_explicit_only():
    items = [decision("BUY", "2026-08-01T09:00:00+09:00", "buy")]
    first = build_investment_episodes(items)
    ref = first["episodes"][0]["entry_decision_ref"]
    second = build_investment_episodes(items, allocation_episode_refs={ref: ["allocation:abc"]})
    assert first["episodes"][0]["allocation_episode_refs"] == []
    assert second["episodes"][0]["allocation_episode_refs"] == ["allocation:abc"]


def test_latest_episode_read_model_points_to_rebuy_episode():
    result = build_investment_episodes(
        [
            decision("BUY", "2026-08-01T09:00:00+09:00", "buy1"),
            decision("SELL", "2026-08-05T09:00:00+09:00", "sell"),
            decision("BUY", "2026-08-10T09:00:00+09:00", "buy2"),
        ],
        portfolio_confirmations=[canonical("NOT_OWNED", "2026-08-05T15:30:00+09:00")],
    )
    assert result["latest_episode_by_security"]["6622"] == result["episodes"][-1]["episode_id"]


def test_deterministic_rerun():
    items = [
        decision("BUY", "2026-08-01T09:00:00+09:00", "buy"),
        decision("HOLD", "2026-08-03T09:00:00+09:00", "hold"),
    ]
    assert build_investment_episodes(items) == build_investment_episodes(deepcopy(items))
