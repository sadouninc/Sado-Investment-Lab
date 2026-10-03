"""Company Episode / Japanese Pages drill-down view over #251 three-axis facts.

This module is the remaining #251 PR4 product-integration slice after PR4A
(execution fidelity learning projection, #820). It projects the existing
``decision_execution_learning_projection`` output onto an Investment Episode
(see ``scripts/investment_episode.py``) so Company Episode drill-downs can
present Decision Quality, Execution Fidelity and Outcome as three
independently visible facts with Japanese explanatory text.

Design constraints (do not relax without a new Issue contract):

* Decision Quality, Execution Fidelity and Outcome are never merged into a
  single score or rolled up into an aggregate episode-level verdict.
* ``UNKNOWN``, ``NOT_JUDGABLE``, ``NOT_EXECUTED`` and ``PARTIAL_MATCH`` are
  always rendered explicitly and are never promoted to ``MATCH`` or any other
  "resolved" state, including when a decision has no learning record at all
  (fail-closed default, not a fabricated fact).
* Canonical refs are only ever copied from explicit input; this module never
  invents a decision/execution/outcome reference.
* This module does not infer decision quality from P/L, does not infer owner
  intent from fills, and never emits a BUY/SELL/HOLD, order instruction, or
  investment recommendation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from scripts.decision_execution_learning_projection import (
    project_execution_fidelity_learning,
)

VIEW_VERSION = "COMPANY_EPISODE_EXECUTION_FIDELITY_VIEW_V1"

FIDELITY_EXPLANATION_JA = (
    "執行の一致度（Execution Fidelity）は、実際の注文が投資判断の内容と"
    "どれだけ一致して執行されたかのみを表す事実です。投資判断の質"
    "（Decision Quality）や結果の良し悪し（Outcome）とは独立しており、"
    "投資の優劣を採点する指標ではありません。"
)

# Fail-closed default axis used only when a decision has no explicit learning
# record. This must never be interpreted as a resolved/positive fact.
_MISSING_AXIS: dict[str, Any] = {"status": "UNKNOWN", "canonical_refs": []}

DECISION_QUALITY_LABELS_JA: dict[str, str] = {
    "SUPPORTED": "裏付けあり",
    "PARTIALLY_SUPPORTED": "一部裏付けあり",
    "NOT_SUPPORTED": "裏付けなし",
    "NOT_JUDGABLE": "判定不能",
    "UNKNOWN": "不明",
}

EXECUTION_FIDELITY_LABELS_JA: dict[str, str] = {
    "MATCH": "一致",
    "PARTIAL_MATCH": "部分一致",
    "MISMATCH": "不一致",
    "NOT_EXECUTED": "未執行",
    "NOT_JUDGABLE": "判定不能",
    "UNKNOWN": "不明",
}

OUTCOME_LABELS_JA: dict[str, str] = {
    "POSITIVE": "好結果",
    "NEGATIVE": "悪化",
    "NEUTRAL": "中立",
    "NOT_JUDGABLE": "判定不能",
    "UNKNOWN": "不明",
}

_AXIS_LABELS = (
    ("decision_quality", DECISION_QUALITY_LABELS_JA),
    ("execution_fidelity", EXECUTION_FIDELITY_LABELS_JA),
    ("outcome", OUTCOME_LABELS_JA),
)


class CompanyEpisodeExecutionFidelityViewError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompanyEpisodeExecutionFidelityViewError(f"{field} must be a non-empty string")
    return value.strip()


def _decision_refs(episode: Mapping[str, Any]) -> list[str]:
    refs = episode.get("decision_refs")
    if not isinstance(refs, (list, tuple)):
        raise CompanyEpisodeExecutionFidelityViewError("episode.decision_refs must be a list")
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise CompanyEpisodeExecutionFidelityViewError(
            "episode.decision_refs must contain non-empty strings"
        )
    return list(refs)


def _label_axis(axis: Mapping[str, Any], labels: Mapping[str, str]) -> dict[str, Any]:
    projected = dict(axis)
    status = projected["status"]
    projected["label_ja"] = labels.get(status, "不明")
    return projected


def _decision_view(
    decision_ref: str,
    learning_records_by_decision: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    raw_record = learning_records_by_decision.get(decision_ref)
    if raw_record is None:
        record: dict[str, Any] = {
            "decision_quality": deepcopy(_MISSING_AXIS),
            "execution_fidelity": deepcopy(_MISSING_AXIS),
            "outcome": deepcopy(_MISSING_AXIS),
        }
    else:
        if not isinstance(raw_record, Mapping):
            raise CompanyEpisodeExecutionFidelityViewError(
                f"learning record for {decision_ref} must be an object"
            )
        record = dict(raw_record)

    try:
        projected = project_execution_fidelity_learning(record)
    except ValueError as exc:
        raise CompanyEpisodeExecutionFidelityViewError(str(exc)) from exc

    view: dict[str, Any] = {"decision_ref": decision_ref}
    for axis_name, labels in _AXIS_LABELS:
        view[axis_name] = _label_axis(projected[axis_name], labels)
    return view


def build_company_episode_execution_fidelity_view(
    episode: Mapping[str, Any],
    learning_records_by_decision: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a Company Episode drill-down view over independent #251 axes.

    ``episode`` is an Investment Episode relation (see
    ``scripts/investment_episode.py``). ``learning_records_by_decision`` maps a
    ``decision_ref`` from ``episode['decision_refs']`` to the raw input of
    ``project_execution_fidelity_learning``. A decision with no entry stays
    explicitly ``UNKNOWN`` on every axis rather than being silently omitted or
    rendered as a resolved fact.

    The returned view never aggregates the three axes into a single score and
    never emits a trade action.
    """
    if not isinstance(episode, Mapping):
        raise CompanyEpisodeExecutionFidelityViewError("episode must be an object")

    episode_ref = _text(episode.get("episode_id"), "episode.episode_id")
    security_code = _text(episode.get("security_code"), "episode.security_code")
    episode_status = _text(episode.get("status"), "episode.status")
    decision_refs = _decision_refs(episode)

    records_map = learning_records_by_decision or {}
    if not isinstance(records_map, Mapping):
        raise CompanyEpisodeExecutionFidelityViewError(
            "learning_records_by_decision must be an object or null"
        )

    decisions = [_decision_view(ref, records_map) for ref in decision_refs]

    return {
        "type": "COMPANY_EPISODE_EXECUTION_FIDELITY_VIEW",
        "view_version": VIEW_VERSION,
        "episode_ref": episode_ref,
        "security_code": security_code,
        "episode_status": episode_status,
        "fidelity_explanation_ja": FIDELITY_EXPLANATION_JA,
        "decisions": decisions,
        "trade_action": None,
    }
