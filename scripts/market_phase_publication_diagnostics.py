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
* ``ARTIFACT_STALE`` – proven stale: a valid manifest date is newer than a
  valid artifact end date, or a manifest symbol is absent from the artifact
* ``FRESHNESS_UNKNOWN`` – freshness could not be decided (manifest not an
  object, or a manifest / artifact date that is not a strict ISO date).  This is
  never reported as stale.
* ``PAGE_PLACEHOLDER_WITH_ARTIFACT`` – page still placeholder although a valid
  artifact exists (build ran before generation, or page is from an old build)
* ``PAGE_SECTIONS_MISSING`` – non-placeholder page lacks expected sections
* ``ROUTE_MISMATCH`` – page front-matter permalink is not the expected route

The report lists every finding, a single ``primary`` code chosen by a fixed
precedence, and ``cause_asserted: false``: findings describe the supplied
inputs, not the root cause of a failure observed elsewhere.

Scope of a passing result: ``structurally_ready: true`` only means the supplied
artifact and page are structurally consistent with what ``build_site`` reads and
writes.  ``freshness`` is ``verified`` only when a price manifest was supplied
and every symbol in it was checked; otherwise it is ``not_checked`` /
``unknown`` / ``stale``.  ``publication_verified`` is always ``false``: this
module never observes the deployed site.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
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
    "FRESHNESS_UNKNOWN",
)

EVIDENCE_LIMITS = (
    "diagnosis covers only the supplied artifact/page/manifest content",
    "no build, pipeline, network or workflow was executed",
    "findings do not establish the root cause of failures observed in other environments",
    "structurally_ready is not verified freshness and not verified publication",
)

_PERMALINK_RE = re.compile(r"^permalink:\s*(\S+)\s*$", re.MULTILINE)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\S+")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_date(value: Any) -> date | None:
    """Strict ``YYYY-MM-DD``; anything else (including a suffix) is ``None``."""

    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """Strict ISO date-time (``YYYY-MM-DDT...``) or ``None``."""

    if not isinstance(value, str) or not _DATETIME_RE.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def front_matter(page_text: str) -> str | None:
    """Return the YAML front-matter block, or ``None`` if the page has none.

    Only a block that starts on the first line with ``---`` and is closed by a
    later ``---`` line counts; text in the page body is never front matter.
    """

    lines = page_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
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
    if _parse_datetime(gen) is None and _parse_date(gen) is None:
        problems.append("generated_at must be a strict ISO date or date-time string")
    universe = report.get("universe")
    if not isinstance(universe, dict) or not _is_int(universe.get("requested")):
        problems.append("universe.requested must be an integer")
    quality = report.get("data_quality")
    if not isinstance(quality, dict):
        problems.append("data_quality must be an object")
    else:
        if not _is_int(quality.get("included")):
            problems.append("data_quality.included must be an integer")
        excluded = quality.get("excluded")
        if not isinstance(excluded, list):
            problems.append("data_quality.excluded must be a list")
        elif not all(isinstance(row, dict) and isinstance(row.get("code"), str) for row in excluded):
            problems.append("data_quality.excluded entries must be objects with a string code")
        if "symbols" in quality:
            seen = quality["symbols"]
            if not isinstance(seen, dict):
                problems.append("data_quality.symbols must be an object")
            elif not all(isinstance(entry, dict) for entry in seen.values()):
                problems.append("data_quality.symbols entries must be objects")
    if not isinstance(report.get("clusters"), dict):
        problems.append("clusters must be an object")
    symbols = report.get("symbols")
    if not isinstance(symbols, list) or not all(
        isinstance(row, dict) and isinstance(row.get("group"), str) for row in symbols
    ):
        problems.append("symbols must be a list of objects with a string group")
    return (report if not problems else None), problems


def _freshness(report: Mapping[str, Any], manifest: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return (proven stale, unknown) details.  ``report`` is already validated."""

    quality = report["data_quality"]
    seen = quality.get("symbols", {})
    excluded = {row["code"] for row in quality["excluded"]}
    stale: list[str] = []
    unknown: list[str] = []
    for code in sorted(manifest, key=str):
        if not isinstance(code, str):
            unknown.append(f"{code!r}: manifest key is not a string")
            continue
        if code in excluded:
            continue
        latest = _parse_date(manifest[code])
        entry = seen.get(code)
        if entry is None:
            stale.append(f"{code}: in price manifest but not in artifact")
        elif latest is None:
            unknown.append(f"{code}: manifest date {manifest[code]!r} is not a strict ISO date")
        elif (end := _parse_date(entry.get("end"))) is None:
            unknown.append(f"{code}: artifact end {entry.get('end')!r} is not a strict ISO date")
        elif end < latest:
            stale.append(f"{code}: artifact end {entry['end']!r} < manifest {manifest[code]!r}")
    return stale, unknown


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
        version = report.get("schema_version") if report is not None else None
        if report is not None and not (_is_int(version) and version == EXPECTED_SCHEMA_VERSION):
            add("ARTIFACT_SCHEMA_MISMATCH", f"schema_version {version!r}")
        if report is not None and price_manifest is not None:
            if not isinstance(price_manifest, Mapping):
                add("FRESHNESS_UNKNOWN", "price manifest is not an object")
            else:
                stale, unknown = _freshness(report, price_manifest)
                for item in stale:
                    add("ARTIFACT_STALE", item)
                for item in unknown:
                    add("FRESHNESS_UNKNOWN", item)

    page_state = "absent"
    if page_text is None:
        add("PAGE_NOT_BUILT", "market-phase page absent")
    else:
        header = front_matter(page_text)
        routes = _PERMALINK_RE.findall(header) if header is not None else []
        if header is None:
            add("ROUTE_MISMATCH", "page has no front matter; permalink unknown")
        elif routes != [EXPECTED_ROUTE]:
            add("ROUTE_MISMATCH", f"front-matter permalink {routes!r} != [{EXPECTED_ROUTE!r}]")
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
    structural = codes.isdisjoint(PRECEDENCE[: PRECEDENCE.index("ARTIFACT_STALE")])
    if report is None or price_manifest is None:
        freshness = "not_checked"
    elif "ARTIFACT_STALE" in codes:
        freshness = "stale"
    elif "FRESHNESS_UNKNOWN" in codes:
        freshness = "unknown"
    else:
        freshness = "verified"
    return {
        "schema": "market_phase_publication_diagnostics_v1",
        "primary": primary,
        "structurally_ready": structural,
        "freshness": freshness,
        "publication_verified": False,
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
    parser.epilog = "exit 0: structurally ready and freshness verified; 1: otherwise; 2: input error"
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
    # 0 only when structure AND freshness were both verified (fail-closed).
    return 0 if report["structurally_ready"] and report["freshness"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
