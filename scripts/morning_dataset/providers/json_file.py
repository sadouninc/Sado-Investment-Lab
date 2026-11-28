from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

from .base import ProviderResult

_MAX_INT_DIGITS = 64
_MAX_JSON_DEPTH = 100


def _bounded_int(text: str) -> int:
    if len(text.lstrip("+-")) > _MAX_INT_DIGITS:
        raise ValueError(f"integer literal longer than {_MAX_INT_DIGITS} digits")
    return int(text)


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    return value


def _reject_constant(_value: str) -> float:
    raise ValueError("non-standard JSON constant is not allowed")


class JsonFileProvider:
    """Deterministic provider for repository-generated JSON sources."""

    def __init__(
        self,
        name: str,
        path: Path,
        *,
        as_of_getter: Callable[[Any], str | None] | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self.as_of_getter = as_of_getter or self._default_as_of

    @staticmethod
    def _default_as_of(data: Any) -> str | None:
        if isinstance(data, dict):
            value = data.get("as_of") or data.get("generated_at")
            return str(value) if value is not None else None
        return None

    def collect(self) -> ProviderResult:
        source_reference = str(self.path)
        if not self.path.is_file():
            return ProviderResult.unavailable(
                self.name,
                reason="source file does not exist",
                source_reference=source_reference,
            )

        try:
            data = json.loads(
                self.path.read_text(encoding="utf-8"),
                parse_int=_bounded_int,
                parse_float=_finite_float,
                parse_constant=_reject_constant,
            )
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                reason=f"source file could not be read: {exc.__class__.__name__}",
                source_reference=source_reference,
            )

        if data is None:
            return ProviderResult.unavailable(
                self.name,
                reason="source JSON contains null",
                source_reference=source_reference,
            )

        if not isinstance(data, (dict, list)):
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                reason="source JSON root must be an object or list",
                source_reference=source_reference,
            )

        if self._contains_unsafe_value(data):
            return ProviderResult.unavailable(
                self.name,
                status="PARTIAL",
                reason="source JSON contains a non-finite value or exceeds the nesting limit",
                source_reference=source_reference,
            )

        return ProviderResult.ok(
            self.name,
            data,
            as_of=self.as_of_getter(data),
            source_reference=source_reference,
        )

    @classmethod
    def _contains_unsafe_value(cls, value: Any) -> bool:
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if isinstance(item, float) and not math.isfinite(item):
                return True
            if depth > _MAX_JSON_DEPTH:
                return True
            if isinstance(item, dict):
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
        return False

