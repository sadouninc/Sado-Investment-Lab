from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

DEPENDENCY_LOCKFILE_PATTERN = re.compile(
    r"(^|/)(package(-lock)?\.json|pyproject\.toml|requirements[^/]*\.txt|poetry\.lock|uv\.lock)$"
)

WORKFLOW_EXACT_PATTERN = re.compile(r"^\.github/workflows/[^/]+\.(yml|yaml)$")


def is_dependency_or_lockfile(path: str) -> bool:
    """Check if path matches forbidden dependency or lockfile patterns."""
    return bool(DEPENDENCY_LOCKFILE_PATTERN.search(path))


def is_generic_forbidden(path: str, allowed_paths: Iterable[str] | None = None) -> bool:
    """Evaluate whether a changed path is generically forbidden.

    - Dependency / lockfile paths are always forbidden.
    - Workflow paths (.github/workflows/...) are forbidden by default.
    - Exception: an exact .github/workflows/<filename>.yml or .yaml path is allowed
      IF AND ONLY IF that exact path string is explicitly present in allowed_paths.
      Wildcards (e.g. .github/workflows/*) in allowed_paths do NOT grant an exception.
    """
    if is_dependency_or_lockfile(path):
        return True

    if path.startswith(".github/workflows/"):
        allowed_list = list(allowed_paths or [])
        if WORKFLOW_EXACT_PATTERN.match(path) and path in allowed_list:
            return False
        return True

    return False


def check_generic_forbidden_paths(
    changed_paths: Iterable[str],
    allowed_paths: Iterable[str] | None = None,
) -> list[str]:
    """Return list of changed paths that violate generic forbidden rules."""
    forbidden = []
    allowed_list = list(allowed_paths or [])
    for path in changed_paths:
        path_str = path.strip()
        if not path_str:
            continue
        if is_generic_forbidden(path_str, allowed_list):
            forbidden.append(path_str)
    return forbidden


def main() -> int:
    parser = argparse.ArgumentParser(description="Copilot harness generic path guard")
    parser.add_argument("--changed-paths-file", type=Path, required=True)
    parser.add_argument("--allowed-paths-file", type=Path, required=False)
    parser.add_argument("--forbidden-paths-output", type=Path, required=False)

    args = parser.parse_args()

    changed_paths = [
        line.strip()
        for line in args.changed_paths_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    allowed_paths = []
    if args.allowed_paths_file and args.allowed_paths_file.exists():
        allowed_paths = [
            line.strip()
            for line in args.allowed_paths_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    forbidden = check_generic_forbidden_paths(changed_paths, allowed_paths)

    if forbidden:
        if args.forbidden_paths_output:
            args.forbidden_paths_output.write_text("\n".join(forbidden) + "\n", encoding="utf-8")
        return 86
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
