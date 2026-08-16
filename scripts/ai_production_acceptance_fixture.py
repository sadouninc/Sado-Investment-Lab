"""Isolated deterministic normalizer fixture for AI Production acceptance.

This module exists only to prove the production routing/terminalization
contract described in Issue #666. It is intentionally isolated from
investment, market, Pages, and workflow semantics: it is a small, pure,
side-effect free helper with no I/O and no external dependencies.
"""

from __future__ import annotations


def normalize_acceptance_token(value: object) -> str | None:
    """Trim outer whitespace from a non-empty string token.

    Fails closed to ``None`` for any non-string input, an empty string, or a
    string that contains only whitespace. Internal characters (including
    internal whitespace) are preserved exactly; only leading/trailing
    whitespace is stripped.
    """
    if not isinstance(value, str):
        return None

    trimmed = value.strip()
    if not trimmed:
        return None

    return trimmed
