"""Exact-head conformance check for a local PR Pages preview artifact (#997).

担当: ♦️ソラ

Validates that a locally available preview artifact (the directory produced by
``.github/pages/prepare_pr_preview.py`` and its ``preview-metadata.json``)
corresponds to the expected pull request, head SHA, optional run/attempt and
required routes. It is read-only and offline: it never fetches, generates or
changes a published URL.

Verdicts:
* ``FAIL``    - evidence contradicts the expectation (wrong PR/head/namespace,
                missing route, path traversal, duplicates, non-preview flags).
* ``UNKNOWN`` - evidence is missing or malformed, or cannot be verified with the
                current metadata schema (e.g. run id/attempt are not recorded).
* ``PASS``    - every check is positively satisfied. This is artifact/metadata
                conformance only; it is not a browser/UX or production check.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from datetime import datetime
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DEFAULT_ROUTES = ("index.html", "concepts/investment-decision-cockpit/index.html", "preview-metadata.json")


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _utc(value: Any) -> bool:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def normalize_path(raw: Any) -> tuple[str | None, str | None]:
    """Return (normalized POSIX relative path, problem). Rejects traversal."""
    if not isinstance(raw, str) or not raw:
        return None, "empty or non-string path"
    if "\x00" in raw or "\\" in raw:
        return None, "NUL or backslash in path"
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return None, "absolute path"
    parts = PurePosixPath(raw).parts
    if any(part == ".." for part in parts):
        return None, "parent traversal"
    clean = [part for part in parts if part not in ("", ".")]
    if not clean:
        return None, "empty after normalization"
    return "/".join(clean), None


def check_files(files: Any) -> tuple[set[str] | None, list[dict[str, str]]]:
    if not isinstance(files, list):
        return None, [_check("files", "UNKNOWN", "artifact file list unavailable")]
    seen: set[str] = set()
    checks: list[dict[str, str]] = []
    for raw in files:
        path, problem = normalize_path(raw)
        if problem:
            checks.append(_check("files.path", "FAIL", f"{problem}: {str(raw)[:120]!r}"))
            continue
        if path in seen:
            checks.append(_check("files.duplicate", "FAIL", f"duplicate path after normalization: {path}"))
            continue
        seen.add(path)
    if not seen and not checks:
        checks.append(_check("files", "UNKNOWN", "artifact is empty"))
    if not checks:
        checks.append(_check("files", "PASS", f"{len(seen)} files, no traversal or duplicates"))
    return seen, checks


def check_artifact(
    metadata: Any,
    files: Any,
    *,
    expected_pr: Any,
    expected_head: Any,
    expected_run_id: Any = None,
    expected_run_attempt: Any = None,
    required_routes: Iterable[Any] = DEFAULT_ROUTES,
) -> dict[str, Any]:
    """Pure conformance check. No I/O."""
    checks: list[dict[str, str]] = []

    if not _positive_int(expected_pr) or not (isinstance(expected_head, str) and _SHA_RE.fullmatch(expected_head)):
        checks.append(_check("expectation", "UNKNOWN", "expected PR number / head SHA missing or malformed"))
        expected_pr, expected_head = None, None

    if not isinstance(metadata, dict):
        checks.append(_check("metadata", "UNKNOWN", "preview-metadata.json unavailable or not an object"))
        metadata = None

    if metadata is not None:
        version = metadata.get("schema_version")
        checks.append(_check("metadata.schema_version", "PASS" if version == SCHEMA_VERSION else "UNKNOWN",
                             f"schema_version={version!r}"))
        for flag in ("preview", "not_production"):
            value = metadata.get(flag)
            status = "PASS" if value is True else ("UNKNOWN" if value is None else "FAIL")
            checks.append(_check(f"metadata.{flag}", status, f"{flag}={value!r}"))

        pr = metadata.get("pull_request")
        if not _positive_int(pr):
            checks.append(_check("metadata.pull_request", "UNKNOWN", f"pull_request={pr!r} not a positive integer"))
        elif expected_pr is not None:
            checks.append(_check("metadata.pull_request", "PASS" if pr == expected_pr else "FAIL",
                                 f"metadata={pr} expected={expected_pr}"))

        head = metadata.get("head_sha")
        if not (isinstance(head, str) and _SHA_RE.fullmatch(head)):
            checks.append(_check("metadata.head_sha", "UNKNOWN", "head_sha missing or not a 40-hex SHA"))
        elif expected_head is not None:
            checks.append(_check("metadata.head_sha", "PASS" if head == expected_head else "FAIL",
                                 "exact head" if head == expected_head else f"stale/mismatched head {head[:12]}"))

        namespace = metadata.get("namespace")
        if not isinstance(namespace, str):
            checks.append(_check("metadata.namespace", "UNKNOWN", "namespace missing"))
        elif expected_pr is None:
            checks.append(_check("metadata.namespace", "UNKNOWN", "no valid expected PR to compare namespace with"))
        else:
            want = f"pr-{expected_pr}"
            checks.append(_check("metadata.namespace", "PASS" if namespace == want else "FAIL",
                                 f"namespace={namespace!r} expected={want!r}"))

        built = metadata.get("built_at")
        checks.append(_check("metadata.built_at", "PASS" if _utc(built) else "UNKNOWN", f"built_at={built!r}"))

        for key, expected in (("run_id", expected_run_id), ("run_attempt", expected_run_attempt)):
            if expected is None:
                continue
            value = metadata.get(key)
            if value is None:
                checks.append(_check(f"metadata.{key}", "UNKNOWN",
                                     f"{key} not recorded by preview metadata schema {SCHEMA_VERSION}"))
            elif not _positive_int(value) or not _positive_int(expected):
                checks.append(_check(f"metadata.{key}", "UNKNOWN", f"{key} malformed"))
            else:
                checks.append(_check(f"metadata.{key}", "PASS" if value == expected else "FAIL",
                                     f"metadata={value} expected={expected}"))

    paths, file_checks = check_files(files)
    checks.extend(file_checks)

    if isinstance(required_routes, (list, tuple)) and required_routes:
        routes = list(required_routes)
    else:
        # The required-route contract cannot be silently emptied or replaced
        # by a malformed value.
        checks.append(_check("route", "UNKNOWN", f"route manifest missing, empty or malformed: {type(required_routes).__name__}"))
        routes = []
    if paths is not None:
        for raw in routes:
            route, problem = normalize_path(raw)
            if problem:
                checks.append(_check("route", "FAIL", f"invalid route manifest entry ({problem}): {str(raw)[:120]!r}"))
            elif route not in paths:
                checks.append(_check("route", "FAIL", f"missing route: {route}"))
            else:
                checks.append(_check("route", "PASS", f"present: {route}"))
        if metadata is not None:
            count = metadata.get("html_files")
            actual = sum(1 for path in paths if path.endswith(".html"))
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                checks.append(_check("metadata.html_files", "UNKNOWN", f"html_files={count!r}"))
            else:
                checks.append(_check("metadata.html_files", "PASS" if count == actual else "FAIL",
                                     f"metadata={count} artifact={actual}"))

    statuses = {item["status"] for item in checks}
    verdict = "FAIL" if "FAIL" in statuses else ("UNKNOWN" if "UNKNOWN" in statuses or not checks else "PASS")
    return {
        "schema_version": 1,
        "verdict": verdict,
        "checks": checks,
        "expected": {
            "pull_request": expected_pr,
            "head_sha": expected_head,
            "run_id": expected_run_id,
            "run_attempt": expected_run_attempt,
        },
        "limits": [
            "local artifact and metadata only; no URL fetched, generated or changed",
            "not a browser, UX or production check",
            f"run id/attempt are not recorded by preview metadata schema {SCHEMA_VERSION}",
        ],
    }


def list_artifact(root: Path) -> list[str] | None:
    """Read-only listing of regular files under ``root``.

    Every symlink (file or directory, internal, dangling, escaping or looping)
    is reported as a traversal entry, which makes the check FAIL; symlinks are
    never followed or resolved. Any enumeration error makes the listing
    unavailable (None -> UNKNOWN) instead of being silently skipped.
    """
    if root.is_symlink() or not root.is_dir():
        return None
    files: list[str] = []
    errors: list[OSError] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=errors.append):
        for name in list(dirnames) + filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()  # os.walk keeps the lexical root prefix
            if full.is_symlink():
                files.append(f"../symlink-rejected/{rel}")  # forces a traversal FAIL
            elif name in filenames and full.is_file():
                files.append(rel)
    if errors:
        return None
    return sorted(files)


def read_metadata(root: Path) -> Any:
    """Read preview-metadata.json only if it is a regular, non-symlink file inside root."""
    path = root / "preview-metadata.json"
    try:
        if root.is_symlink() or path.is_symlink() or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PR preview artifact exact-head conformance (#997)")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-pr", type=int, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-run-id", type=int)
    parser.add_argument("--expected-run-attempt", type=int)
    parser.add_argument("--route", action="append", dest="routes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = check_artifact(
        read_metadata(args.root),
        list_artifact(args.root),
        expected_pr=args.expected_pr,
        expected_head=args.expected_head,
        expected_run_id=args.expected_run_id,
        expected_run_attempt=args.expected_run_attempt,
        required_routes=args.routes or DEFAULT_ROUTES,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
