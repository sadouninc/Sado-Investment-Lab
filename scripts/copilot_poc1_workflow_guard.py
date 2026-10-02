"""Generic forbidden-path guard for the Copilot PoC1 harness.

Dependency/lockfile paths are always forbidden. Workflow paths are forbidden
by default. Issue #830 permits only an explicitly contracted exact
.github/workflows/<file>.yml or .yaml path to proceed to normal Contract
validation; wildcard entries never qualify.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

_WORKFLOW_PREFIX = ".github/workflows/"
_EXACT_WORKFLOW_FILE = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")
_DEPENDENCY_FILE = re.compile(r"(^|/)(package(-lock)?\.json|pyproject\.toml|requirements[^/]*\.txt|poetry\.lock|uv\.lock)$")
_GLOB_CHARS = ("*", "?", "[")

def _is_literal_path(pattern: str) -> bool:
    return not any(char in pattern for char in _GLOB_CHARS)

def is_exact_workflow_exception(path: str, allowed_paths: list[str]) -> bool:
    if not _EXACT_WORKFLOW_FILE.match(path):
        return False
    return any(entry == path and _is_literal_path(entry) for entry in allowed_paths)

def generic_forbidden_paths(changed_paths: list[str], allowed_paths: list[str]) -> list[str]:
    forbidden: list[str] = []
    for path in changed_paths:
        if path.startswith(_WORKFLOW_PREFIX):
            if not is_exact_workflow_exception(path, allowed_paths):
                forbidden.append(path)
            continue
        if _DEPENDENCY_FILE.search(path):
            forbidden.append(path)
    return forbidden

def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-paths", type=Path, required=True)
    parser.add_argument("--allowed-paths", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    forbidden = generic_forbidden_paths(_read_lines(args.changed_paths), _read_lines(args.allowed_paths))
    if forbidden:
        args.output.write_text("\n".join(forbidden) + "\n", encoding="utf-8")
        return 86
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
