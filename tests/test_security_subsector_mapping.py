from copy import deepcopy

import jsonschema
import pytest

from scripts.security_subsector_mapping import lookup_security_subsector, validate_mapping

TAXONOMY = "existing-canonical-ref-v1"


def record(*, code="6702", subsector="technology-services", status="MAPPED", start="2026-01-01", end=None, refs=None):
    return {
        "security_code": code,
        "subsector_id": subsector if status == "MAPPED" else None,
        "taxonomy_version": TAXONOMY,
        "effective_from": start,
        "effective_to": end,
        "status": status,
        "source_refs": ["fixture:#756"] if refs is None else refs,
        "as_of": "2026-08-21",
    }


def mapping(records):
    return {"schema_version": 1, "taxonomy_version": TAXONOMY, "records": records}


def test_valid_mapped_record_and_lookup():
    source = mapping([record()])
    validate_mapping(source)
    result = lookup_security_subsector("6702", "2026-08-21", TAXONOMY, source)
    assert result["status"] == "MAPPED"
    assert result["subsector_id"] == "technology-services"


def test_valid_unmapped_record_preserves_unknown_semantics():
    source = mapping([record(code="9999", status="UNMAPPED", subsector=None, refs=[])])
    validate_mapping(source)
    result = lookup_security_subsector("9999", "2026-08-21", TAXONOMY, source)
    assert result["status"] == "UNMAPPED"
    assert result["subsector_id"] is None


def test_mapped_record_requires_evidence():
    source = mapping([record(refs=[])])
    with pytest.raises(jsonschema.ValidationError):
        validate_mapping(source)


def test_effective_range_boundaries_are_inclusive_and_gap_is_unknown():
    source = mapping([
        record(start="2026-01-01", end="2026-03-31"),
        record(subsector="software", start="2026-04-02", end=None),
    ])
    assert lookup_security_subsector("6702", "2026-01-01", TAXONOMY, source)["status"] == "MAPPED"
    assert lookup_security_subsector("6702", "2026-03-31", TAXONOMY, source)["status"] == "MAPPED"
    assert lookup_security_subsector("6702", "2026-04-01", TAXONOMY, source)["status"] == "NO_EFFECTIVE_RECORD"
    assert lookup_security_subsector("6702", "2026-04-02", TAXONOMY, source)["subsector_id"] == "software"


def test_overlapping_effective_ranges_fail_closed():
    source = mapping([
        record(start="2026-01-01", end="2026-06-30"),
        record(subsector="software", start="2026-06-30", end=None),
    ])
    with pytest.raises(ValueError, match="overlapping active mappings"):
        validate_mapping(source)


def test_taxonomy_mismatch_returns_explicit_state_without_fallback():
    source = mapping([record()])
    result = lookup_security_subsector("6702", "2026-08-21", "future-taxonomy-v2", source)
    assert result == {
        "status": "TAXONOMY_MISMATCH",
        "security_code": "6702",
        "subsector_id": None,
        "taxonomy_version": TAXONOMY,
    }


def test_record_taxonomy_must_match_top_level_taxonomy():
    source = mapping([record()])
    broken = deepcopy(source)
    broken["records"][0]["taxonomy_version"] = "other-v1"
    with pytest.raises(ValueError, match="record taxonomy_version"):
        validate_mapping(broken)


def test_no_security_record_is_not_inferred():
    source = mapping([])
    result = lookup_security_subsector("4588", "2026-08-21", TAXONOMY, source)
    assert result["status"] == "NO_EFFECTIVE_RECORD"
    assert result["subsector_id"] is None
