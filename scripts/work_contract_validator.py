from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


REQUIRED_FIELDS = (
    "version",
    "goal",
    "status",
    "owner_slice",
    "risk",
    "authority",
    "dependencies",
    "allowed_paths",
    "forbidden_paths",
    "acceptance_tests",
    "expected_outputs",
    "human_gate",
    "non_goals",
)

VALID_RISKS = {"GREEN", "YELLOW", "RED"}
VALID_AUTHORITIES = {"STANDARD", "OWNER_REQUIRED", "PROHIBITED"}
PROTECTED_GREEN_PATHS = ("TEAM_RULES.md", "TEAM_STATE.md", ".github/")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    executable: bool
    errors: tuple[str, ...]
    contract: dict[str, Any] | None


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(item) for item in inner.split(",")]
    if value.isdigit():
        return int(value)
    return value


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the deliberately small Work Contract v1 YAML subset.

    The contract is intentionally flat except for top-level lists. Refuse nested
    mappings instead of guessing. This keeps the validator dependency-free and
    deterministic across agent runtimes.
    """
    result: dict[str, Any] = {}
    current_list: str | None = None

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            if not key:
                raise ValueError("empty key")
            parsed = _scalar(value)
            result[key] = parsed
            current_list = key if value.strip() == "" else None
            if current_list:
                result[current_list] = []
            continue
        if indent > 0 and line.startswith("-") and current_list:
            result[current_list].append(_scalar(line[1:]))
            continue
        raise ValueError(f"unsupported YAML structure: {line}")
    return result


def extract_work_contract(issue_body: str) -> dict[str, Any]:
    if not isinstance(issue_body, str):
        raise ValueError("issue body must be text")
    blocks = re.findall(r"```(?:yaml|yml)\s*\n(.*?)```", issue_body, flags=re.DOTALL | re.IGNORECASE)
    candidates: list[dict[str, Any]] = []
    for block in blocks:
        lines = block.splitlines()
        for index, line in enumerate(lines):
            if line.strip() != "work_contract:":
                continue
            nested: list[str] = []
            for child in lines[index + 1 :]:
                if not child.strip():
                    nested.append(child)
                    continue
                indent = len(child) - len(child.lstrip(" "))
                if indent == 0:
                    break
                nested.append(child[2:] if child.startswith("  ") else child.lstrip())
            candidates.append(_parse_simple_yaml("\n".join(nested)))
    if not candidates:
        raise ValueError("work_contract fenced YAML block not found")
    if len(candidates) != 1:
        raise ValueError("exactly one work_contract is required")
    return candidates[0]


def _path_prefix(path: str) -> str:
    """Return the fixed (non-wildcard) prefix of a path or glob pattern.

    A previous implementation only stripped trailing ``*`` characters, so a
    pattern with a wildcard followed by a literal suffix (for example
    ``scripts/*.py``) was returned unchanged. That silently defeated overlap
    detection against forbidden paths such as
    ``scripts/operational_state_guard.py``: the two strings never share a
    startswith relationship, so a genuine allowed/forbidden overlap could
    pass validation undetected. Truncating at the first wildcard character
    instead keeps the directory-prefix comparison correct for any glob shape.
    """
    text = str(path).strip()
    for index, char in enumerate(text):
        if char in "*?[":
            return text[:index]
    return text


def _paths_overlap(left: str, right: str) -> bool:
    a, b = _path_prefix(left), _path_prefix(right)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))


def validate_contract(contract: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    missing = [field for field in REQUIRED_FIELDS if field not in contract]
    errors.extend(f"MISSING_FIELD:{field}" for field in missing)

    if contract.get("version") != 1:
        errors.append("UNSUPPORTED_VERSION")
    if contract.get("status") != "READY_FOR_IMPLEMENTATION":
        errors.append("NOT_READY")
    if contract.get("risk") not in VALID_RISKS:
        errors.append("INVALID_RISK")
    if contract.get("authority") not in VALID_AUTHORITIES:
        errors.append("INVALID_AUTHORITY")

    list_fields = (
        "dependencies",
        "allowed_paths",
        "forbidden_paths",
        "acceptance_tests",
        "expected_outputs",
        "human_gate",
        "non_goals",
    )
    for field in list_fields:
        if field in contract and not isinstance(contract[field], list):
            errors.append(f"INVALID_LIST:{field}")

    tests = contract.get("acceptance_tests")
    if isinstance(tests, list) and not tests:
        errors.append("EMPTY_ACCEPTANCE_TESTS")

    allowed = contract.get("allowed_paths", [])
    forbidden = contract.get("forbidden_paths", [])
    if isinstance(allowed, list) and isinstance(forbidden, list):
        for left in allowed:
            for right in forbidden:
                if _paths_overlap(str(left), str(right)):
                    errors.append("ALLOWED_FORBIDDEN_OVERLAP")
                    break

    if contract.get("risk") == "GREEN" and isinstance(allowed, list):
        for path in allowed:
            normalized = _path_prefix(str(path))
            if any(_paths_overlap(normalized, protected) for protected in PROTECTED_GREEN_PATHS):
                errors.append(f"GREEN_PROTECTED_PATH:{path}")
            if re.search(r"(^|[/_.-])79([/_.-]|$)", normalized, flags=re.IGNORECASE):
                errors.append(f"GREEN_ISSUE_79_PATH:{path}")

    unique_errors = tuple(sorted(set(errors)))
    valid = not unique_errors
    executable = valid and contract.get("status") == "READY_FOR_IMPLEMENTATION"
    return ValidationResult(valid, executable, unique_errors, contract)


def validate_issue_body(issue_body: str) -> ValidationResult:
    try:
        contract = extract_work_contract(issue_body)
    except ValueError as exc:
        return ValidationResult(False, False, (f"PARSE_ERROR:{exc}",), None)
    return validate_contract(contract)
