"""Tests for scripts.diagnostic_text.normalize_optional_diagnostic_text."""

import pytest

from scripts.diagnostic_text import normalize_optional_diagnostic_text


def test_none_returns_none():
    assert normalize_optional_diagnostic_text(None) is None


def test_empty_string_returns_none():
    assert normalize_optional_diagnostic_text("") is None


def test_whitespace_only_returns_none():
    assert normalize_optional_diagnostic_text("  \t\n") is None


def test_nonblank_string_is_trimmed():
    assert (
        normalize_optional_diagnostic_text("  BLOCKED_NO_REPO_DIFF  ")
        == "BLOCKED_NO_REPO_DIFF"
    )


def test_internal_spacing_preserved():
    assert (
        normalize_optional_diagnostic_text("  reason:  keep  internal spacing  ")
        == "reason:  keep  internal spacing"
    )


@pytest.mark.parametrize("value", [1, 1.5, [], {}, ["a"], {"a": 1}, True])
def test_non_string_input_raises_type_error(value):
    with pytest.raises(TypeError):
        normalize_optional_diagnostic_text(value)


def test_deterministic_repeated_calls():
    value = "  duplicate check  "
    first = normalize_optional_diagnostic_text(value)
    second = normalize_optional_diagnostic_text(value)
    assert first == second == "duplicate check"
