from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class BOJSignalState(str, Enum):
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    RED = "RED"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    AMBIGUOUS = "AMBIGUOUS"
    MISSING = "MISSING"


class EvidenceType(str, Enum):
    STATEMENT = "STATEMENT"
    SUMMARY_OF_OPINIONS = "SUMMARY_OF_OPINIONS"
    OUTLOOK_REPORT = "OUTLOOK_REPORT"
    GOVERNOR_SPEECH = "GOVERNOR_SPEECH"
    MEMBER_SPEECH = "MEMBER_SPEECH"
    OFFICIAL_RATE_HIKE = "OFFICIAL_RATE_HIKE"
    OTHER = "OTHER"


def _normalize_status(val: Any) -> str:
    if isinstance(val, EvidenceStatus):
        return val.value.upper()
    if hasattr(val, "value"):
        return str(val.value).upper()
    return str(val or "MISSING").upper()


def _normalize_type(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, EvidenceType):
        return val.value.upper()
    if hasattr(val, "value"):
        return str(val.value).upper()
    return str(val).upper()


@dataclass(frozen=True)
class BOJEvidenceRef:
    ref_id: str
    source_title: str
    evidence_type: str
    url_or_path: str = ""
    as_of: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "source_title": self.source_title,
            "evidence_type": _normalize_type(self.evidence_type) or "OTHER",
            "url_or_path": self.url_or_path,
            "as_of": self.as_of,
        }


@dataclass
class BOJEvidenceInput:
    primary_evidence_present: bool = False
    evidence_status: str | EvidenceStatus = EvidenceStatus.MISSING
    evidence_type: str | EvidenceType | None = None
    indicates_near_term_tightening: bool = False
    actual_rate_hike_decision: bool = False
    evidence_refs: list[BOJEvidenceRef] = field(default_factory=list)
    is_stale: bool = False
    notes: str = ""


@dataclass
class BOJMarketFactorsInput:
    market_implied_probability: float | None = None
    market_probability_only: bool = False
    inflation_upside: bool = False
    hawkish_breadth_expanding: bool = False
    market_prob_rising: bool = False
    macro_pressures: bool = False


@dataclass
class BOJSignalInput:
    primary_evidence: BOJEvidenceInput = field(default_factory=BOJEvidenceInput)
    market_factors: BOJMarketFactorsInput = field(default_factory=BOJMarketFactorsInput)
    as_of: str = ""
    raw_requested_state: str | None = None


@dataclass
class BOJSignalResult:
    signal_state: str
    effective_state: str
    raw_requested_state: str
    primary_evidence_present: bool
    probability_only: bool
    evidence_refs: list[dict[str, Any]]
    reason: str
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_evidence_input(data: Any) -> BOJEvidenceInput:
    if not isinstance(data, dict):
        return BOJEvidenceInput()

    refs_data = data.get("evidence_refs", [])
    parsed_refs: list[BOJEvidenceRef] = []
    if isinstance(refs_data, list):
        for ref in refs_data:
            if isinstance(ref, BOJEvidenceRef):
                parsed_refs.append(ref)
            elif isinstance(ref, dict):
                parsed_refs.append(
                    BOJEvidenceRef(
                        ref_id=str(ref.get("ref_id") or ""),
                        source_title=str(ref.get("source_title") or ""),
                        evidence_type=str(ref.get("evidence_type") or "OTHER"),
                        url_or_path=str(ref.get("url_or_path") or ""),
                        as_of=str(ref.get("as_of") or ""),
                    )
                )

    status_str = _normalize_status(data.get("evidence_status") or data.get("status"))
    ev_type_str = _normalize_type(data.get("evidence_type"))

    return BOJEvidenceInput(
        primary_evidence_present=bool(data.get("primary_evidence_present") or data.get("present")),
        evidence_status=status_str,
        evidence_type=ev_type_str,
        indicates_near_term_tightening=bool(data.get("indicates_near_term_tightening")),
        actual_rate_hike_decision=bool(data.get("actual_rate_hike_decision")),
        evidence_refs=parsed_refs,
        is_stale=bool(data.get("is_stale")),
        notes=str(data.get("notes") or ""),
    )


def _parse_market_factors_input(data: Any) -> BOJMarketFactorsInput:
    if not isinstance(data, dict):
        return BOJMarketFactorsInput()

    prob = data.get("market_implied_probability")
    prob_float: float | None = None
    if prob is not None and not isinstance(prob, (bool, list, dict, set, tuple)):
        try:
            val = float(prob)
            if not (val != val):  # exclude NaN
                prob_float = val
        except (ValueError, TypeError):
            prob_float = None

    return BOJMarketFactorsInput(
        market_implied_probability=prob_float,
        market_probability_only=bool(data.get("market_probability_only") or data.get("probability_only")),
        inflation_upside=bool(data.get("inflation_upside")),
        hawkish_breadth_expanding=bool(data.get("hawkish_breadth_expanding")),
        market_prob_rising=bool(data.get("market_prob_rising")),
        macro_pressures=bool(data.get("macro_pressures")),
    )


def classify_boj_signal(signal_input: BOJSignalInput | dict[str, Any] | None) -> BOJSignalResult:
    """Classify BOJ early warning policy signal state deterministically.

    Invariants & Rules:
    1. Market-implied probability alone MUST NEVER classify RED.
    2. RED requires valid current primary BOJ evidence indicating near-term tightening
       or an actual rate-hike decision.
    3. Missing / ambiguous / stale primary evidence must NOT become RED and must preserve
       UNKNOWN / insufficient-evidence semantics when primary evidence is required.
    4. ORANGE represents elevated multi-factor risk without asserting a near-term policy decision,
       or caps probability-only signals that attempt RED.
    5. Output contains evidence references/provenance and emits no BUY/SELL/HOLD recommendations.
    6. Deterministic output: same input produces identical output.
    """
    if signal_input is None:
        return BOJSignalResult(
            signal_state=BOJSignalState.UNKNOWN.value,
            effective_state=BOJSignalState.UNKNOWN.value,
            raw_requested_state="NONE",
            primary_evidence_present=False,
            probability_only=True,
            evidence_refs=[],
            reason="No input provided; failing closed to UNKNOWN.",
            provenance={"input_type": "None"},
        )

    if isinstance(signal_input, BOJSignalInput):
        primary_ev = signal_input.primary_evidence
        market_fact = signal_input.market_factors
        as_of = signal_input.as_of
        raw_requested = signal_input.raw_requested_state or "UNSPECIFIED"
    elif isinstance(signal_input, dict):
        primary_ev = _parse_evidence_input(signal_input.get("primary_evidence") or signal_input)
        market_fact = _parse_market_factors_input(signal_input.get("market_factors") or signal_input)
        as_of = str(signal_input.get("as_of") or "")
        raw_requested = str(signal_input.get("raw_requested_state") or signal_input.get("signal_state") or "UNSPECIFIED").upper()
    else:
        return BOJSignalResult(
            signal_state=BOJSignalState.UNKNOWN.value,
            effective_state=BOJSignalState.UNKNOWN.value,
            raw_requested_state="INVALID_TYPE",
            primary_evidence_present=False,
            probability_only=True,
            evidence_refs=[],
            reason=f"Unsupported signal input type '{type(signal_input)}'; failing closed to UNKNOWN.",
            provenance={"input_type": str(type(signal_input))},
        )

    # Status evaluation
    status_norm = _normalize_status(primary_ev.evidence_status)
    ev_type_norm = _normalize_type(primary_ev.evidence_type)
    is_stale = primary_ev.is_stale or (status_norm == "STALE")
    is_ambiguous = status_norm == "AMBIGUOUS"
    is_missing = status_norm == "MISSING" or not primary_ev.primary_evidence_present
    is_valid_primary = (
        primary_ev.primary_evidence_present
        and status_norm == "VALID"
        and not is_stale
    )

    # Multi-factor counting
    factor_signals = [
        market_fact.inflation_upside,
        market_fact.hawkish_breadth_expanding,
        market_fact.market_prob_rising,
        market_fact.macro_pressures,
    ]
    multi_factor_count = sum(1 for s in factor_signals if s)
    prob_val = market_fact.market_implied_probability
    has_high_market_prob = (prob_val is not None and prob_val >= 0.5) or market_fact.market_prob_rising

    probability_only = (
        market_fact.market_probability_only
        or not is_valid_primary
    )

    refs_serialized = [
        ref.to_dict() if isinstance(ref, BOJEvidenceRef) else ref
        for ref in primary_ev.evidence_refs
    ]

    provenance = {
        "as_of": as_of,
        "primary_evidence_present": primary_ev.primary_evidence_present,
        "evidence_status": status_norm,
        "evidence_type": ev_type_norm,
        "indicates_near_term_tightening": primary_ev.indicates_near_term_tightening,
        "actual_rate_hike_decision": primary_ev.actual_rate_hike_decision,
        "is_stale": is_stale,
        "probability_only": probability_only,
        "multi_factor_count": multi_factor_count,
        "market_implied_probability": prob_val,
    }

    # Deterministic Classifier Core Logic
    # 1. Actual rate hike decision
    if is_valid_primary and primary_ev.actual_rate_hike_decision:
        return BOJSignalResult(
            signal_state=BOJSignalState.RED.value,
            effective_state=BOJSignalState.RED.value,
            raw_requested_state=raw_requested,
            primary_evidence_present=True,
            probability_only=False,
            evidence_refs=refs_serialized,
            reason="Actual BOJ rate-hike decision confirmed by current valid primary evidence.",
            provenance=provenance,
        )

    # 2. Current valid primary BOJ evidence indicating near-term tightening
    if is_valid_primary and primary_ev.indicates_near_term_tightening:
        return BOJSignalResult(
            signal_state=BOJSignalState.RED.value,
            effective_state=BOJSignalState.RED.value,
            raw_requested_state=raw_requested,
            primary_evidence_present=True,
            probability_only=False,
            evidence_refs=refs_serialized,
            reason="Current valid primary BOJ evidence explicitly indicates near-term tightening.",
            provenance=provenance,
        )

    # 3. Handling requested RED or invalid/missing/stale/ambiguous primary evidence
    if raw_requested == "RED" or primary_ev.indicates_near_term_tightening or primary_ev.actual_rate_hike_decision:
        # RED was requested or implied, but primary evidence condition failed
        if is_stale:
            reason = "Primary BOJ evidence is stale; cannot classify RED without current valid primary evidence."
        elif is_ambiguous:
            reason = "Primary BOJ evidence is ambiguous; cannot classify RED without explicit tightening indication."
        elif is_missing:
            reason = "Primary BOJ evidence is missing; market-implied probability alone must never classify RED."
        else:
            reason = f"Primary evidence status '{status_norm}' invalid for RED classification."

        if multi_factor_count >= 2 or has_high_market_prob:
            return BOJSignalResult(
                signal_state=BOJSignalState.ORANGE.value,
                effective_state=BOJSignalState.ORANGE.value,
                raw_requested_state=raw_requested,
                primary_evidence_present=primary_ev.primary_evidence_present,
                probability_only=probability_only,
                evidence_refs=refs_serialized,
                reason=f"[CAPPED_AT_ORANGE] {reason} Multi-factor risk elevated.",
                provenance=provenance,
            )
        else:
            return BOJSignalResult(
                signal_state=BOJSignalState.UNKNOWN.value,
                effective_state=BOJSignalState.UNKNOWN.value,
                raw_requested_state=raw_requested,
                primary_evidence_present=primary_ev.primary_evidence_present,
                probability_only=probability_only,
                evidence_refs=refs_serialized,
                reason=f"[FAIL_CLOSED] {reason} Insufficient primary evidence and multi-factor context.",
                provenance=provenance,
            )

    # 4. Multi-factor elevated risk => ORANGE
    if multi_factor_count >= 2 or has_high_market_prob:
        return BOJSignalResult(
            signal_state=BOJSignalState.ORANGE.value,
            effective_state=BOJSignalState.ORANGE.value,
            raw_requested_state=raw_requested,
            primary_evidence_present=primary_ev.primary_evidence_present,
            probability_only=probability_only,
            evidence_refs=refs_serialized,
            reason="Elevated multi-factor risk detected without asserting a near-term policy decision.",
            provenance=provenance,
        )

    # 5. Missing or stale or ambiguous primary evidence with no multi-factor risk => UNKNOWN or GREEN
    if primary_ev.primary_evidence_present and (is_stale or is_ambiguous):
        return BOJSignalResult(
            signal_state=BOJSignalState.UNKNOWN.value,
            effective_state=BOJSignalState.UNKNOWN.value,
            raw_requested_state=raw_requested,
            primary_evidence_present=True,
            probability_only=probability_only,
            evidence_refs=refs_serialized,
            reason=f"Primary evidence is {status_norm.lower()}; failing closed to UNKNOWN.",
            provenance=provenance,
        )

    # 6. Default baseline => GREEN
    return BOJSignalResult(
        signal_state=BOJSignalState.GREEN.value,
        effective_state=BOJSignalState.GREEN.value,
        raw_requested_state=raw_requested,
        primary_evidence_present=primary_ev.primary_evidence_present,
        probability_only=probability_only,
        evidence_refs=refs_serialized,
        reason="Primary evidence of near-term tightening is weak/absent and multi-factor risk is low.",
        provenance=provenance,
    )
