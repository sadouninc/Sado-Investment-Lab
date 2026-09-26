import pytest

from scripts.productivity_output_classification import classify_productivity_output


@pytest.mark.parametrize(
    ("duplicate", "noop", "classification", "counted"),
    [
        ("TRUE", "FALSE", "DUPLICATE", True),
        ("FALSE", "TRUE", "NO_OP", True),
        ("TRUE", "TRUE", "DUPLICATE", True),
        ("FALSE", "FALSE", "PRODUCTIVE_CANDIDATE", False),
        ("UNKNOWN", "FALSE", "UNKNOWN", None),
        ("FALSE", "UNKNOWN", "UNKNOWN", None),
        ("UNKNOWN", "UNKNOWN", "UNKNOWN", None),
    ],
)
def test_explicit_evidence_classification(duplicate, noop, classification, counted):
    result = classify_productivity_output(
        duplicate_evidence=duplicate,
        noop_evidence=noop,
    )
    assert result["classification"] == classification
    assert result["count_as_duplicate_or_noop"] is counted


def test_evidence_refs_preserve_order_and_content():
    refs = ["issue:689", {"kind": "review", "id": 42}, "pr:123"]
    result = classify_productivity_output(
        duplicate_evidence="FALSE",
        noop_evidence="FALSE",
        evidence_refs=refs,
    )
    assert result["evidence_refs"] == refs


def test_same_input_produces_same_output():
    kwargs = {
        "duplicate_evidence": "UNKNOWN",
        "noop_evidence": "FALSE",
        "evidence_refs": ["ref:a", "ref:b"],
    }
    assert classify_productivity_output(**kwargs) == classify_productivity_output(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"noop_evidence": "FALSE"},
        {"duplicate_evidence": "FALSE"},
        {"duplicate_evidence": "INVALID", "noop_evidence": "FALSE"},
        {"duplicate_evidence": "FALSE", "noop_evidence": ""},
        {"duplicate_evidence": None, "noop_evidence": "FALSE"},
    ],
)
def test_missing_or_invalid_evidence_is_validation_error(kwargs):
    with pytest.raises((TypeError, ValueError)):
        classify_productivity_output(**kwargs)


def test_classifier_does_not_mutate_evidence_refs():
    refs = ["a", "b"]
    original = list(refs)
    classify_productivity_output(
        duplicate_evidence="TRUE",
        noop_evidence="UNKNOWN",
        evidence_refs=refs,
    )
    assert refs == original
