from copy import deepcopy

from scripts.market_compass_security_intraday_evidence import (
    resolve_security_intraday_evidence,
)

TAXONOMY = "v1.2"


def mapping(status="MAPPED", subsector="sub_semi_equip", taxonomy=TAXONOMY):
    return {
        "schema_version": 1,
        "records": [
            {
                "security_code": "8035",
                "subsector_id": subsector if status == "MAPPED" else None,
                "taxonomy_version": taxonomy,
                "effective_from": "2026-01-01",
                "effective_to": None,
                "status": status,
                "source_refs": ["fixture:#586"] if status == "MAPPED" else [],
                "as_of": "2026-08-21",
            }
        ],
    }


def evidence(*, freshness="FRESH", completeness="COMPLETE", subsector="sub_semi_equip", taxonomy=TAXONOMY):
    return {
        "schema_version": 1,
        "observed_at": "2026-08-21T00:30:00Z",
        "source": "fixture",
        "freshness": freshness,
        "data_completeness": completeness,
        "benchmark": "TOPIX",
        "sector": {"id": "sec_tech", "label": "Technology", "medium_term_regime": "EXPANSION"},
        "subsector": {
            "id": subsector,
            "label": "Semiconductor Equipment",
            "taxonomy_version": taxonomy,
            "as_of": "2026-08-21T00:30:00Z",
            "source_or_authority": "fixture-taxonomy",
        },
        "observations": {
            "intraday_return": 0.02,
            "benchmark_return": 0.005,
            "relative_return": 0.015,
            "rising_count": 8,
            "constituent_count": 10,
            "breadth": 0.8,
            "median_constituent_return": 0.018,
            "turnover_ratio": 1.1,
            "concentration_top1": 0.3,
        },
        "leaders": [],
        "flow_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
    }


def test_mapped_fresh_complete_projects_read_only_evidence():
    result = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, evidence(), mapping())
    assert result["status"] == "PASS"
    assert result["mapping"]["subsector_id"] == "sub_semi_equip"
    assert result["intraday_evidence"]["data_quality"]["status"] == "PASS"
    assert result["investment_authority"] == "READ_ONLY_EVIDENCE"
    assert result["trade_recommendation"] is None


def test_unmapped_fails_closed_without_consuming_evidence():
    result = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, evidence(), mapping(status="UNMAPPED"))
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "UNMAPPED"
    assert result["intraday_evidence"] is None


def test_taxonomy_mismatch_fails_closed():
    result = resolve_security_intraday_evidence("8035", "2026-08-21", "v2", evidence(), mapping())
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "TAXONOMY_MISMATCH"


def test_subsector_evidence_mismatch_fails_closed():
    result = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, evidence(subsector="other"), mapping())
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "SUBSECTOR_EVIDENCE_MISMATCH"
    assert result["intraday_evidence"] is None


def test_stale_or_partial_evidence_never_becomes_pass():
    stale = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, evidence(freshness="STALE"), mapping())
    partial = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, evidence(completeness="PARTIAL"), mapping())
    assert (stale["status"], stale["reason"]) == ("UNKNOWN", "STALE")
    assert (partial["status"], partial["reason"]) == ("UNKNOWN", "PARTIAL")


def test_inputs_are_not_mutated():
    source_mapping = mapping()
    source_evidence = evidence()
    before_mapping = deepcopy(source_mapping)
    before_evidence = deepcopy(source_evidence)
    resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, source_evidence, source_mapping)
    assert source_mapping == before_mapping
    assert source_evidence == before_evidence


def test_malformed_adapter_result_missing_subsector_fails_closed():
    malformed = {"schema_version": 1, "observed_at": "2026-08-21T00:30:00Z"}
    result = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, malformed, mapping())
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "INVALID_EVIDENCE_FORMAT"
    assert result["intraday_evidence"] is None


def test_missing_data_quality_status_fails_closed():
    malformed_evidence = evidence()
    malformed_evidence["data_quality"] = {}
    result = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, malformed_evidence, mapping())
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "INVALID_EVIDENCE_STRUCTURE"
    assert result["intraday_evidence"] is None


def test_missing_subsector_id_in_mapping_fails_closed():
    bad_mapping = mapping()
    del bad_mapping["records"][0]["subsector_id"]
    result = resolve_security_intraday_evidence("8035", "2026-08-21", TAXONOMY, evidence(), bad_mapping)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "INVALID_MAPPING_OR_EVIDENCE"
    assert result["intraday_evidence"] is None
