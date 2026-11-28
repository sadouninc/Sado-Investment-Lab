"""Read-only diagnostics for Market Phase page publication (#873, #1004).

``.github/pages/test_build_site.py::test_market_phase_report_is_published``
expects the built page ``site-src/research/market-phase/ai-semiconductor/index.md``
to contain the full analyzer sections.  ``build_market_phase()`` in
``.github/pages/build_site.py`` writes only a "分析データを生成中です"
placeholder when the generated artifact
``data/generated/public/market-phase/ai-semiconductor.json`` is absent.  That
artifact is git-ignored and produced by ``python3 -m
scripts.market_phase.pipeline``, so a plain checkout that skips the generation
step fails the test while CI (which generates first) passes.

This module distinguishes such situations from synthetic or captured inputs
without changing the build, the test, any workflow or any published output:

* ``ARTIFACT_NOT_GENERATED`` – artifact absent (page placeholder is expected)
* ``PAGE_NOT_BUILT`` – page absent
* ``ARTIFACT_MALFORMED`` – artifact not JSON or missing fields build_site reads
* ``ARTIFACT_SCHEMA_MISMATCH`` – unexpected ``schema_version``
* ``ARTIFACT_STALE`` – price manifest has newer dates / symbols not reflected
* ``PAGE_PLACEHOLDER_WITH_ARTIFACT`` – page still placeholder although a valid
  artifact exists (build ran before generation, or page is from an old build)
* ``PAGE_SECTIONS_MISSING`` – non-placeholder page lacks expected sections
* ``ROUTE_MISMATCH`` – page front-matter permalink is not the expected route

The report lists every finding, a single ``primary`` code chosen by a fixed
precedence, and ``cause_asserted: false``: findings describe the supplied
inputs, not the root cause of a failure observed elsewhere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping

EXPECTED_ROUTE = "/research/market-phase/ai-semiconductor/"
PLACEHOLDER_MARKER = "分析データを生成中です"
EXPECTED_PAGE_MARKERS = (
    "Sado Market Phase Analyzer",
    "正規化比較チャート",
    "相関ヒートマップ",
    'id="phase-data"',
    "先行・遅行候補",
)
EXPECTED_SCHEMA_VERSION = 1

PRECEDENCE = (
    "PAGE_NOT_BUILT",
    "ARTIFACT_NOT_GENERATED",
    "ARTIFACT_MALFORMED",
    "ARTIFACT_SCHEMA_MISMATCH",
    "ROUTE_MISMATCH",
    "PAGE_PLACEHOLDER_WITH_ARTIFACT",
    "PAGE_SECTIONS_MISSING",
    "ARTIFACT_STALE",
)

EVIDENCE_LIMITS = (
    "diagnosis covers only the supplied artifact/page/manifest content",
    "no build, pipeline, network or workflow was executed",
    "findings do not establish the root cause of failures observed in other environments",
)

_PERMALINK_RE = re.compile(r"^permalink:\s*(\S+)\s*$", re.MULTILINE)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def check_artifact(text: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (parsed artifact, problems) against the fields build_site reads."""

    try:
        report = json.loads(text)
    except (ValueError, RecursionError):
        return None, ["artifact is not valid JSON"]
    if not isinstance(report, dict):
        return None, ["artifact is not a JSON object"]
    problems: list[str] = []
    gen = report.get("generated_at")
    if not isinstance(gen, str) or _parse_date(gen) is None:
        problems.append("generated_at must be an ISO date/time string")
    universe = report.get("universe")
    if not isinstance(universe, dict) or not _is_int(universe.get("requested")):
        problems.append("universe.requested must be an integer")
    quality = report.get("data_quality")
    if not isinstance(quality, dict):
        problems.append("data_quality must be an object")
    else:
        if not _is_int(quality.get("included")):
            problems.append("data_quality.included must be an integer")
        if not isinstance(quality.get("excluded"), list):
            problems.append("data_quality.excluded must be a list")
        if "symbols" in quality and not isinstance(quality["symbols"], dict):
            problems.append("data_quality.symbols must be an object")
    if not isinstance(report.get("clusters"), dict):
        problems.append("clusters must be an object")
    symbols = report.get("symbols")
    if not isinstance(symbols, list) or not all(
        isinstance(row, dict) and isinstance(row.get("group"), str) for row in symbols
    ):
        problems.append("symbols must be a list of objects with a string group")
    return (report if not problems else None), problems


def _stale_symbols(report: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[str]:
    quality = report.get("data_quality", {})
    seen = quality.get("symbols", {}) if isinstance(quality.get("symbols"), dict) else {}
    excluded = {
        row.get("code") for row in quality.get("excluded", []) if isinstance(row, dict)
    }
    stale: list[str] = []
    for code in sorted(manifest):
        latest = _parse_date(manifest[code])
        if code in excluded:
            continue
        entry = seen.get(code)
        end = _parse_date(entry.get("end")) if isinstance(entry, dict) else None
        if entry is None:
            stale.append(f"{code}: in price manifest but not in artifact")
        elif latest is None:
            stale.append(f"{code}: manifest date unreadable")
        elif end is None or end < latest:
            stale.append(f"{code}: artifact end {entry.get('end')!r} < manifest {manifest[code]!r}")
    return stale


def diagnose(
    *,
    artifact_text: str | None,
    page_text: str | None,
    price_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify publication state. ``None`` means the file does not exist."""

    findings: list[dict[str, Any]] = []

    def add(code: str, detail: str) -> None:
        findings.append({"code": code, "detail": detail})

    report: dict[str, Any] | None = None
    if artifact_text is None:
        add("ARTIFACT_NOT_GENERATED", "market-phase artifact absent; run scripts.market_phase.pipeline before build")
    else:
        report, problems = check_artifact(artifact_text)
        for problem in problems:
            add("ARTIFACT_MALFORMED", problem)
        if report is not None and report.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            add("ARTIFACT_SCHEMA_MISMATCH", f"schema_version {report.get('schema_version')!r}")
        if report is not None and price_manifest is not None:
            if not isinstance(price_manifest, Mapping):
                add("ARTIFACT_STALE", "price manifest unreadable; freshness unknown")
            else:
                for item in _stale_symbols(report, price_manifest):
                    add("ARTIFACT_STALE", item)

    page_state = "absent"
    if page_text is None:
        add("PAGE_NOT_BUILT", "market-phase page absent")
    else:
        match = _PERMALINK_RE.search(page_text)
        if not match or match.group(1) != EXPECTED_ROUTE:
            add("ROUTE_MISMATCH", f"permalink {match.group(1) if match else None!r} != {EXPECTED_ROUTE!r}")
        missing = [m for m in EXPECTED_PAGE_MARKERS if m not in page_text]
        if PLACEHOLDER_MARKER in page_text:
            page_state = "placeholder"
            if report is not None:
                add("PAGE_PLACEHOLDER_WITH_ARTIFACT", "valid artifact exists but page shows the generation placeholder")
        else:
            page_state = "full" if not missing else "incomplete"
            if missing:
                add("PAGE_SECTIONS_MISSING", "missing: " + ", ".join(missing))

    codes = {f["code"] for f in findings}
    primary = next((c for c in PRECEDENCE if c in codes), "OK")
    findings.sort(key=lambda f: (PRECEDENCE.index(f["code"]), f["detail"]))
    return {
        "schema": "market_phase_publication_diagnostics_v1",
        "primary": primary,
        "publishable": primary == "OK",
        "artifact_state": "absent" if artifact_text is None else ("valid" if report is not None else "invalid"),
        "page_state": page_state,
        "findings": findings,
        "cause_asserted": False,
        "evidence_limits": list(EVIDENCE_LIMITS),
    }


def _read_optional(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--page", type=Path, required=True)
    parser.add_argument("--price-manifest", type=Path, help='JSON {"<code>": "YYYY-MM-DD", ...}')
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = None
        if args.price_manifest is not None:
            manifest = json.loads(args.price_manifest.read_text(encoding="utf-8"))
        report = diagnose(
            artifact_text=_read_optional(args.artifact),
            page_text=_read_optional(args.page),
            price_manifest=manifest,
        )
    except (OSError, ValueError, UnicodeDecodeError, RecursionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["publishable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
