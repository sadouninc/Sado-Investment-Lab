from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Direction = Literal["IMPROVED", "UNCHANGED", "DETERIORATED", "UNKNOWN"]
Scenario = Literal["Bear", "Base", "Bull", "UNKNOWN"]
ValuationDirection = Literal["EXPANDED", "UNCHANGED", "NARROWED", "UNKNOWN"]


@dataclass(frozen=True)
class ScenarioSnapshot:
    scenario: Scenario
    eps: float | None
    price: float | None
    forward_per: float | None
    premise: str | None = None


@dataclass(frozen=True)
class ScenarioDelta:
    previous: ScenarioSnapshot
    current: ScenarioSnapshot
    earnings_direction: Direction
    price_direction: Direction
    valuation_direction: ValuationDirection
    scenario_transition: str
    summary_ja: str


def _compare(previous: float | None, current: float | None) -> Direction:
    if previous is None or current is None:
        return "UNKNOWN"
    if current > previous:
        return "IMPROVED"
    if current < previous:
        return "DETERIORATED"
    return "UNCHANGED"


def _valuation_compare(previous: float | None, current: float | None) -> ValuationDirection:
    """Lower Forward PER means valuation headroom expanded; higher means narrowed."""
    if previous is None or current is None:
        return "UNKNOWN"
    if current < previous:
        return "EXPANDED"
    if current > previous:
        return "NARROWED"
    return "UNCHANGED"


def _transition(previous: Scenario, current: Scenario) -> str:
    if previous == "UNKNOWN" or current == "UNKNOWN":
        return "UNKNOWN"
    if previous == current:
        return f"{previous}維持"
    return f"{previous}→{current}"


def _summary_ja(
    earnings_direction: Direction,
    price_direction: Direction,
    valuation_direction: ValuationDirection,
) -> str:
    if "UNKNOWN" in {earnings_direction, price_direction, valuation_direction}:
        return "前回との差分を確定するための情報が不足しています。"
    if earnings_direction == "IMPROVED" and price_direction == "IMPROVED" and valuation_direction == "NARROWED":
        return "業績見通しは改善しましたが、株価上昇が大きく、valuation余地は縮小しています。"
    if earnings_direction == "IMPROVED" and valuation_direction == "EXPANDED":
        return "業績見通しが改善し、valuation余地も拡大しています。"
    if earnings_direction == "DETERIORATED" and valuation_direction == "NARROWED":
        return "業績見通しが悪化し、valuation余地も縮小しています。"
    return "前回判断からの業績・株価・valuation変化を確認してください。"


def build_scenario_delta(previous: ScenarioSnapshot, current: ScenarioSnapshot) -> ScenarioDelta:
    """Build a read-only comparison without mutating either snapshot."""
    earnings_direction = _compare(previous.eps, current.eps)
    price_direction = _compare(previous.price, current.price)
    valuation_direction = _valuation_compare(previous.forward_per, current.forward_per)
    return ScenarioDelta(
        previous=previous,
        current=current,
        earnings_direction=earnings_direction,
        price_direction=price_direction,
        valuation_direction=valuation_direction,
        scenario_transition=_transition(previous.scenario, current.scenario),
        summary_ja=_summary_ja(earnings_direction, price_direction, valuation_direction),
    )
