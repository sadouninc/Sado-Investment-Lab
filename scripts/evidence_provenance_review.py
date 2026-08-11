from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from scripts.evidence_provenance import ProvenanceLedger, ProvenanceValidationError

_ALLOWED_TRANSITIONS = {
    "CURRENT": {"CORRECTED", "SUPERSEDED", "UNAVAILABLE"},
    "CORRECTED": {"SUPERSEDED", "UNAVAILABLE"},
    "SUPERSEDED": set(),
    "UNAVAILABLE": set(),
}


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


@dataclass(frozen=True)
class SourceTransition:
    transition_id: str
    source_id: str
    from_status: str
    to_status: str
    reason_code: str
    replacement_source_id: str | None = None


@dataclass(frozen=True)
class FactSupersession:
    relation_id: str
    old_fact_id: str
    new_fact_id: str


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    left_ref: str
    right_ref: str
    reason_code: str
    status: str = "NEEDS_REVIEW"


@dataclass(frozen=True)
class ReviewCandidate:
    review_id: str
    trigger_type: str
    subject_ref: str
    reason_codes: tuple[str, ...]
    affected_refs: tuple[str, ...]
    status: str = "NEEDS_REVIEW"


class ProvenanceReviewIndex:
    """Append-only correction/conflict overlay for the #144 provenance contract.

    The underlying ProvenanceLedger remains immutable. This index records state
    transitions, fact supersession and unresolved conflicts without rewriting
    historical SourceRecord / FactRecord payloads.
    """

    def __init__(self, ledger: ProvenanceLedger) -> None:
        self.ledger = ledger
        self._source_transitions: dict[str, SourceTransition] = {}
        self._fact_supersessions: dict[str, FactSupersession] = {}
        self._conflicts: dict[str, ConflictRecord] = {}

    def _source(self, source_id: str):
        source = self.ledger._sources.get(source_id)
        if source is None:
            raise ProvenanceValidationError(f"source is not registered: {source_id}")
        return source

    def _fact(self, fact_id: str):
        fact = self.ledger._facts.get(fact_id)
        if fact is None:
            raise ProvenanceValidationError(f"fact is not registered: {fact_id}")
        return fact

    def source_status(self, source_id: str) -> str:
        source = self._source(source_id)
        current = source.status
        transitions = [
            item for item in self._source_transitions.values() if item.source_id == source_id
        ]
        # Transition ids are deterministic. A source can only advance through the
        # allowed one-way state graph, so replaying the stored transitions reaches
        # the same terminal status without mutating the historical SourceRecord.
        remaining = list(transitions)
        while remaining:
            advanced = False
            for item in sorted(remaining, key=lambda item: item.transition_id):
                if item.from_status == current:
                    current = item.to_status
                    remaining.remove(item)
                    advanced = True
                    break
            if not advanced:
                break
        return current

    def transition_source(
        self,
        *,
        source_id: str,
        to_status: str,
        reason_code: str,
        replacement_source_id: str | None = None,
    ) -> SourceTransition:
        self._source(source_id)
        target = str(to_status).strip().upper()
        reason = str(reason_code).strip().upper()
        if not reason:
            raise ProvenanceValidationError("reason_code is required")
        if replacement_source_id is not None:
            self._source(replacement_source_id)
            if replacement_source_id == source_id:
                raise ProvenanceValidationError("replacement source must differ")

        # Exact logical retries are idempotent even after the source has already
        # advanced to the target state.
        for existing in self._source_transitions.values():
            if (
                existing.source_id == source_id
                and existing.to_status == target
                and existing.reason_code == reason
                and existing.replacement_source_id == replacement_source_id
            ):
                return existing

        current = self.source_status(source_id)
        if target not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise ProvenanceValidationError(
                f"invalid source transition: {current} -> {target}"
            )
        identity_payload = {
            "source_id": source_id,
            "from_status": current,
            "to_status": target,
            "reason_code": reason,
            "replacement_source_id": replacement_source_id,
        }
        item = SourceTransition(
            transition_id=_stable_id("source-transition", identity_payload),
            source_id=source_id,
            from_status=current,
            to_status=target,
            reason_code=reason,
            replacement_source_id=replacement_source_id,
        )
        self._source_transitions[item.transition_id] = item
        return item

    def supersede_fact(self, *, old_fact_id: str, new_fact_id: str) -> FactSupersession:
        old = self._fact(old_fact_id)
        new = self._fact(new_fact_id)
        if old_fact_id == new_fact_id:
            raise ProvenanceValidationError("fact cannot supersede itself")
        if (old.entity_type, old.entity_id, old.field, old.period) != (
            new.entity_type,
            new.entity_id,
            new.field,
            new.period,
        ):
            raise ProvenanceValidationError("superseding fact must describe the same fact key")
        payload = {"old_fact_id": old_fact_id, "new_fact_id": new_fact_id}
        item = FactSupersession(
            relation_id=_stable_id("fact-supersession", payload),
            old_fact_id=old_fact_id,
            new_fact_id=new_fact_id,
        )
        return self._fact_supersessions.setdefault(item.relation_id, item)

    def register_conflict(
        self, *, left_ref: str, right_ref: str, reason_code: str
    ) -> ConflictRecord:
        if left_ref == right_ref:
            raise ProvenanceValidationError("conflict refs must differ")
        known = set(self.ledger._sources) | set(self.ledger._facts)
        if left_ref not in known or right_ref not in known:
            raise ProvenanceValidationError("conflict refs must be registered")
        left, right = sorted((left_ref, right_ref))
        reason = str(reason_code).strip().upper()
        if not reason:
            raise ProvenanceValidationError("reason_code is required")
        payload = {"left_ref": left, "right_ref": right, "reason_code": reason}
        item = ConflictRecord(
            conflict_id=_stable_id("provenance-conflict", payload),
            left_ref=left,
            right_ref=right,
            reason_code=reason,
        )
        return self._conflicts.setdefault(item.conflict_id, item)

    def affected_refs(self, subject_ref: str) -> tuple[str, ...]:
        known_sources = set(self.ledger._sources)
        known_facts = set(self.ledger._facts)
        if subject_ref not in known_sources | known_facts:
            raise ProvenanceValidationError(f"unknown provenance ref: {subject_ref}")

        roots = {subject_ref}
        if subject_ref in known_sources:
            roots.update(
                fact.fact_id
                for fact in self.ledger._facts.values()
                if fact.source_id == subject_ref
            )
        affected = {
            edge.to_id
            for edge in self.ledger._edges.values()
            if edge.from_id in roots
        }
        return tuple(sorted(affected))

    def build_review_candidate(self, subject_ref: str) -> ReviewCandidate:
        reasons: set[str] = set()
        if subject_ref in self.ledger._sources:
            status = self.source_status(subject_ref)
            if status in {"CORRECTED", "SUPERSEDED", "UNAVAILABLE"}:
                reasons.add(f"SOURCE_{status}")
        elif subject_ref not in self.ledger._facts:
            raise ProvenanceValidationError(f"unknown provenance ref: {subject_ref}")

        related = {subject_ref}
        if subject_ref in self.ledger._sources:
            related.update(
                fact.fact_id
                for fact in self.ledger._facts.values()
                if fact.source_id == subject_ref
            )
        for conflict in self._conflicts.values():
            if conflict.left_ref in related or conflict.right_ref in related:
                reasons.add("SOURCE_CONFLICT")

        if not reasons:
            raise ProvenanceValidationError("subject has no review-triggering provenance state")
        affected = self.affected_refs(subject_ref)
        payload = {
            "trigger_type": "SOURCE_CORRECTION_REVIEW",
            "subject_ref": subject_ref,
            "reason_codes": sorted(reasons),
            "affected_refs": list(affected),
        }
        return ReviewCandidate(
            review_id=_stable_id("review-candidate", payload),
            trigger_type="SOURCE_CORRECTION_REVIEW",
            subject_ref=subject_ref,
            reason_codes=tuple(sorted(reasons)),
            affected_refs=affected,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_transitions": [
                asdict(self._source_transitions[key])
                for key in sorted(self._source_transitions)
            ],
            "fact_supersessions": [
                asdict(self._fact_supersessions[key])
                for key in sorted(self._fact_supersessions)
            ],
            "conflicts": [asdict(self._conflicts[key]) for key in sorted(self._conflicts)],
        }
