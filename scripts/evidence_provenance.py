from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SOURCE_TYPES = {
    "IR",
    "FILING",
    "GOVERNMENT",
    "MARKET_DATA",
    "NEWS",
    "POLICY",
    "INTERNAL_RESEARCH",
}
SOURCE_AUTHORITIES = {"PRIMARY", "SECONDARY", "INTERNAL"}
SOURCE_STATUSES = {"CURRENT", "SUPERSEDED", "CORRECTED", "UNAVAILABLE"}
FACT_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
LINEAGE_RELATIONS = {
    "SUPPORTS",
    "CHALLENGES",
    "INVALIDATES",
    "DERIVED_FROM",
    "REFERENCES",
    "SUPERSEDES",
}
FACT_INTERPRETATION_FIELDS = {
    "interpretation",
    "impact",
    "hypothesis",
    "opinion",
    "conclusion",
    "recommendation",
}


class ProvenanceValidationError(ValueError):
    """Raised when a provenance record violates the canonical contract."""


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ProvenanceValidationError(f"{field} is required")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _timestamp(value: Any, field: str, *, required: bool = True) -> str | None:
    """Validate and canonicalize an instant to UTC ISO-8601.

    Equivalent timestamp spellings (for example ``Z`` vs ``+00:00`` or a
    different offset representing the same instant) must serialize identically
    before they participate in deterministic identities.
    """

    text = _required_text(value, field) if required else _optional_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProvenanceValidationError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ProvenanceValidationError(f"{field} must include timezone information")
    return parsed.astimezone(timezone.utc).isoformat()


def _date(value: Any, field: str) -> str:
    text = _required_text(value, field)
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ProvenanceValidationError(f"{field} must be YYYY-MM-DD") from exc
    return text


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    text = _required_text(value, field).upper()
    if text not in allowed:
        raise ProvenanceValidationError(
            f"unsupported {field}: {text}; allowed={sorted(allowed)}"
        )
    return text


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:24]}"


def deterministic_source_id(
    *,
    source_type: str,
    publisher: str,
    published_at: str,
    canonical_ref: str,
    content_hash: str | None = None,
) -> str:
    """Return a stable identity for one published source/document.

    observed_at is deliberately excluded: observing the same source twice must not
    create two source identities. An optional content hash distinguishes a replaced
    document served through otherwise identical metadata.
    """

    payload = {
        "source_type": _enum(source_type, "source_type", SOURCE_TYPES),
        "publisher": _required_text(publisher, "publisher"),
        "published_at": _timestamp(published_at, "published_at"),
        "canonical_ref": _required_text(canonical_ref, "canonical_ref"),
        "content_hash": _optional_text(content_hash),
    }
    return _stable_id("source", payload)


def deterministic_fact_id(
    *,
    source_id: str,
    entity_type: str,
    entity_id: str,
    field: str,
    period: str,
) -> str:
    """Return a stable identity for a structured fact from one source."""

    payload = {
        "source_id": _required_text(source_id, "source_id"),
        "entity_type": _required_text(entity_type, "entity_type").upper(),
        "entity_id": _required_text(entity_id, "entity_id"),
        "field": _required_text(field, "field"),
        "period": _required_text(period, "period"),
    }
    return _stable_id("fact", payload)


def deterministic_edge_id(*, from_id: str, to_id: str, relation: str) -> str:
    """Return a stable identity for one logical lineage relationship."""

    payload = {
        "from": _required_text(from_id, "from"),
        "to": _required_text(to_id, "to"),
        "relation": _enum(relation, "relation", LINEAGE_RELATIONS),
    }
    return _stable_id("edge", payload)


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_type: str
    publisher: str
    published_at: str
    observed_at: str
    canonical_ref: str
    content_hash: str | None
    authority: str
    status: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "SourceRecord":
        allowed = {
            "source_id",
            "source_type",
            "publisher",
            "published_at",
            "observed_at",
            "canonical_ref",
            "content_hash",
            "authority",
            "status",
        }
        _reject_unknown(raw, allowed, "SourceRecord")
        source_type = _enum(raw.get("source_type"), "source_type", SOURCE_TYPES)
        publisher = _required_text(raw.get("publisher"), "publisher")
        published_at = _timestamp(raw.get("published_at"), "published_at")
        observed_at = _timestamp(raw.get("observed_at"), "observed_at")
        canonical_ref = _required_text(raw.get("canonical_ref"), "canonical_ref")
        content_hash = _optional_text(raw.get("content_hash"))
        expected = deterministic_source_id(
            source_type=source_type,
            publisher=publisher,
            published_at=published_at,
            canonical_ref=canonical_ref,
            content_hash=content_hash,
        )
        supplied = _optional_text(raw.get("source_id"))
        if supplied is not None and supplied != expected:
            raise ProvenanceValidationError("source_id does not match deterministic identity")
        return cls(
            source_id=expected,
            source_type=source_type,
            publisher=publisher,
            published_at=published_at,
            observed_at=observed_at,
            canonical_ref=canonical_ref,
            content_hash=content_hash,
            authority=_enum(raw.get("authority"), "authority", SOURCE_AUTHORITIES),
            status=_enum(raw.get("status"), "status", SOURCE_STATUSES),
        )


@dataclass(frozen=True)
class FactRecord:
    fact_id: str
    source_id: str
    entity_type: str
    entity_id: str
    field: str
    value: Any
    unit: str | None
    period: str
    as_of: str
    locator: str | None
    confidence: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "FactRecord":
        contaminated = sorted(FACT_INTERPRETATION_FIELDS.intersection(raw))
        if contaminated:
            raise ProvenanceValidationError(
                "FactRecord cannot contain interpretation fields: " + ", ".join(contaminated)
            )
        allowed = {
            "fact_id",
            "source_id",
            "entity_type",
            "entity_id",
            "field",
            "value",
            "unit",
            "period",
            "as_of",
            "locator",
            "confidence",
        }
        _reject_unknown(raw, allowed, "FactRecord")
        source_id = _required_text(raw.get("source_id"), "source_id")
        entity_type = _required_text(raw.get("entity_type"), "entity_type").upper()
        entity_id = _required_text(raw.get("entity_id"), "entity_id")
        field = _required_text(raw.get("field"), "field")
        period = _required_text(raw.get("period"), "period")
        expected = deterministic_fact_id(
            source_id=source_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field=field,
            period=period,
        )
        supplied = _optional_text(raw.get("fact_id"))
        if supplied is not None and supplied != expected:
            raise ProvenanceValidationError("fact_id does not match deterministic identity")
        if "value" not in raw:
            raise ProvenanceValidationError("value is required; use null when explicitly unknown")
        return cls(
            fact_id=expected,
            source_id=source_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field=field,
            value=deepcopy(raw.get("value")),
            unit=_optional_text(raw.get("unit")),
            period=period,
            as_of=_date(raw.get("as_of"), "as_of"),
            locator=_optional_text(raw.get("locator")),
            confidence=_enum(raw.get("confidence"), "confidence", FACT_CONFIDENCE),
        )


@dataclass(frozen=True)
class LineageEdge:
    edge_id: str
    from_id: str
    to_id: str
    relation: str
    created_at: str
    actor: str
    note: str | None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LineageEdge":
        allowed = {"edge_id", "from", "to", "relation", "created_at", "actor", "note"}
        _reject_unknown(raw, allowed, "LineageEdge")
        from_id = _required_text(raw.get("from"), "from")
        to_id = _required_text(raw.get("to"), "to")
        if from_id == to_id:
            raise ProvenanceValidationError("lineage edge cannot point to itself")
        relation = _enum(raw.get("relation"), "relation", LINEAGE_RELATIONS)
        expected = deterministic_edge_id(from_id=from_id, to_id=to_id, relation=relation)
        supplied = _optional_text(raw.get("edge_id"))
        if supplied is not None and supplied != expected:
            raise ProvenanceValidationError("edge_id does not match deterministic identity")
        return cls(
            edge_id=expected,
            from_id=from_id,
            to_id=to_id,
            relation=relation,
            created_at=_timestamp(raw.get("created_at"), "created_at"),
            actor=_required_text(raw.get("actor"), "actor").upper(),
            note=_optional_text(raw.get("note")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["from"] = payload.pop("from_id")
        payload["to"] = payload.pop("to_id")
        return payload


def _reject_unknown(raw: Mapping[str, Any], allowed: set[str], record_name: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ProvenanceValidationError(
            f"{record_name} contains unsupported fields: {', '.join(unknown)}"
        )


class ProvenanceLedger:
    """In-memory idempotent registry used by adapters and tests.

    PR1 intentionally defines contract semantics only. Persistence adapters are a
    later slice; consumers may serialize ``to_dict()`` into their own canonical
    storage without changing identity semantics.
    """

    def __init__(self) -> None:
        self._sources: dict[str, SourceRecord] = {}
        self._facts: dict[str, FactRecord] = {}
        self._edges: dict[str, LineageEdge] = {}

    def ingest_source(self, raw: Mapping[str, Any]) -> SourceRecord:
        return self._insert(self._sources, SourceRecord.from_mapping(raw), "source_id")

    def ingest_fact(self, raw: Mapping[str, Any]) -> FactRecord:
        record = FactRecord.from_mapping(raw)
        if record.source_id not in self._sources:
            raise ProvenanceValidationError(
                f"fact source_id is not registered: {record.source_id}"
            )
        return self._insert(self._facts, record, "fact_id")

    def ingest_edge(self, raw: Mapping[str, Any]) -> LineageEdge:
        record = LineageEdge.from_mapping(raw)
        known = set(self._sources) | set(self._facts)
        if record.from_id not in known:
            raise ProvenanceValidationError(f"lineage from is not registered: {record.from_id}")
        # ``to`` may point to a downstream Hypothesis / Decision record owned by
        # another SSoT, so it is intentionally not required to exist in this ledger.
        return self._insert(self._edges, record, "edge_id")

    @staticmethod
    def _insert(store: dict[str, Any], record: Any, identity_field: str) -> Any:
        identity = getattr(record, identity_field)
        existing = store.get(identity)
        if existing is None:
            store[identity] = record
            return record
        if existing == record:
            return existing
        raise ProvenanceValidationError(
            f"conflicting payload for existing deterministic identity: {identity}"
        )

    def ingest(
        self,
        *,
        sources: Iterable[Mapping[str, Any]] = (),
        facts: Iterable[Mapping[str, Any]] = (),
        edges: Iterable[Mapping[str, Any]] = (),
    ) -> dict[str, int]:
        for raw in sources:
            self.ingest_source(raw)
        for raw in facts:
            self.ingest_fact(raw)
        for raw in edges:
            self.ingest_edge(raw)
        return {
            "sources": len(self._sources),
            "facts": len(self._facts),
            "edges": len(self._edges),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sources": [asdict(self._sources[key]) for key in sorted(self._sources)],
            "facts": [asdict(self._facts[key]) for key in sorted(self._facts)],
            "edges": [self._edges[key].to_dict() for key in sorted(self._edges)],
        }
