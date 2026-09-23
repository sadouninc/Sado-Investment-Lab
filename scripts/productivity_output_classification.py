"""Pure deterministic duplicate/no-op evidence classifier for productivity KPI v2."""

from __future__ import annotations

from typing import Any, Iterable


EVIDENCE_VALUES = frozenset({"TRUE", "FALSE", "UNKNOWN"})


def _validate_evidence(name: str, value: Any) -> str:
    if value not in EVIDENCE_VALUES:
        raise ValueError(
            f"{name} must be one of {sorted(EVIDENCE_VALUES)}, got {value!r}"
        )
    return value


def classify_productivity_output(
    *,
    duplicate_evidence: str,
    noop_evidence: str,
    evidence_refs: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Classify only from explicit evidence; UNKNOWN never becomes productive.

    ``PRODUCTIVE_CANDIDATE`` means only that duplicate/no-op evidence is
    explicitly false. Durable/productive-output qualification is a separate
    contract.
    """

    duplicate = _validate_evidence("duplicate_evidence", duplicate_evidence)
    noop = _validate_evidence("noop_evidence", noop_evidence)

    refs = [] if evidence_refs is None else list(evidence_refs)

    if duplicate == "TRUE":
        classification = "DUPLICATE"
        count_as_duplicate_or_noop: bool | None = True
    elif noop == "TRUE":
        classification = "NO_OP"
        count_as_duplicate_or_noop = True
    elif duplicate == "FALSE" and noop == "FALSE":
        classification = "PRODUCTIVE_CANDIDATE"
        count_as_duplicate_or_noop = False
    else:
        classification = "UNKNOWN"
        count_as_duplicate_or_noop = None

    return {
        "classification": classification,
        "count_as_duplicate_or_noop": count_as_duplicate_or_noop,
        "evidence_refs": refs,
    }
