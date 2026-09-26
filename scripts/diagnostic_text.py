"""Pure helper for normalizing optional diagnostic text.

This helper is deliberately isolated from investment logic, workflows,
routing, portfolio state, and provider harness semantics. It exists to
prevent whitespace-only text from being treated as meaningful evidence
while preserving nonblank text deterministically.
"""

from __future__ import annotations

from typing import Optional


def normalize_optional_diagnostic_text(value: Optional[str]) -> Optional[str]:
    """Normalize optional diagnostic/status/reason text.

    Contract:
        - ``None`` -> ``None``
        - empty string -> ``None``
        - whitespace-only string -> ``None``
        - nonblank string -> trim only leading/trailing whitespace,
          preserving internal content exactly
        - non-string input -> raise ``TypeError``

    This function is pure and deterministic: no I/O, network, environment,
    timestamp, or repository mutation.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(
            "normalize_optional_diagnostic_text expects None or str, "
            f"got {type(value).__name__}"
        )

    stripped = value.strip()
    if stripped == "":
        return None

    return stripped
