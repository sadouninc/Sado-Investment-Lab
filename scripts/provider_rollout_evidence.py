"""Read-only dependency-evidence checker for strict-JSON rollouts (#972, #1002).

The Morning Dataset strict validator (#976) may only land after the provider
hardening PRs it depends on (for example #974 for events) are merged, and
after a combined integration run (#982) has exercised exactly those refs.
Reviewers have been checking this by hand from PR pages, CI pages and
integration comments.  This module turns that check into a deterministic,
testable report built from a *snapshot* JSON document.

Input document (local JSON, no network)::

    {
      "target":       {"pr": 976, "head_sha": "<40 hex>"},
      "dependencies": [{"pr": 974, "provider": "events"}, ...],
      "prs":          [{"number": 974, "state": "closed", "merged": true,
                         "head_sha": "<40 hex>", "merge_commit_sha": "<40 hex>"}, ...],
      "ci":           {"head_sha": "<40 hex>",
                        "required_checks": ["build", "preflight"],
                        "checks": [{"name": "build", "conclusion": "success"}, ...]},
      "integration":  {"base_sha": "<40 hex>",
                        "refs": [{"pr": 974, "sha": "<40 hex>"},
                                 {"pr": 976, "sha": "<40 hex>"}],
                        "passed": 9, "failed": 0, "errors": 0}
    }

Rules (each failure is a HOLD reason; nothing is ever PASS by default):

* every dependency must have exactly one PR snapshot that is merged with a
  well-formed ``merge_commit_sha``;
* the integration run must list each dependency at its merge SHA (or at its
  final head SHA when that equals the merged head) and the target at its
  current head; an older target head is ``STALE_TARGET_HEAD``;
* the integration run must report ``passed > 0`` with zero failures/errors;
* CI must be for the current target head and every required check must have
  concluded ``success``;
* duplicate or contradictory entries and malformed values are HOLD.

The report always carries ``merge_authorized: false``.  Even
``EVIDENCE_COMPLETE`` only means the listed evidence is internally
consistent; review, Flow Authority gate and GitHub enforcement still decide.

Exit codes: ``0`` = EVIDENCE_COMPLETE, ``1`` = HOLD, ``2`` = unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

STATUS_COMPLETE = "EVIDENCE_COMPLETE"
STATUS_HOLD = "HOLD"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

EVIDENCE_LIMITS = (
    "input is a caller-supplied snapshot; live PR/CI state was not fetched",
    "git ancestry of base_sha against dependency merge SHAs was not verified",
    "snapshot authorship is not authenticated",
    "EVIDENCE_COMPLETE is not a review, CI PASS or merge approval",
)


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.match(value))


def _is_pr(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _hold(reasons: list[dict[str, Any]], code: str, detail: str, **ref: Any) -> None:
    entry: dict[str, Any] = {"code": code, "detail": detail}
    entry.update(ref)
    reasons.append(entry)


def build_report(doc: Any) -> dict[str, Any]:
    """Build a deterministic rollout-evidence report. Never raises on bad content."""

    reasons: list[dict[str, Any]] = []
    deps_out: list[dict[str, Any]] = []
    target_pr: int | None = None
    target_head: str | None = None

    if not isinstance(doc, dict):
        _hold(reasons, "MALFORMED", "document must be a JSON object")
        doc = {}

    # --- target ------------------------------------------------------------
    target = doc.get("target")
    if not isinstance(target, dict) or not _is_pr(target.get("pr")) or not _is_sha(target.get("head_sha")):
        _hold(reasons, "MALFORMED", "target must have positive integer pr and 40-hex head_sha")
    else:
        target_pr, target_head = target["pr"], target["head_sha"]

    # --- PR snapshots --------------------------------------------------------
    snapshots: dict[int, dict[str, Any]] = {}
    prs = doc.get("prs", [])
    if not isinstance(prs, list):
        _hold(reasons, "MALFORMED", "prs must be a list")
        prs = []
    for pos, snap in enumerate(prs):
        if not isinstance(snap, dict) or not _is_pr(snap.get("number")):
            _hold(reasons, "MALFORMED", f"prs[{pos}] must be an object with positive integer number")
            continue
        num = snap["number"]
        if num in snapshots:
            if json.dumps(snapshots[num], sort_keys=True) != json.dumps(snap, sort_keys=True):
                _hold(reasons, "CONFLICTING_SNAPSHOT", f"PR #{num} has contradictory snapshots", pr=num)
            else:
                _hold(reasons, "DUPLICATE_SNAPSHOT", f"PR #{num} listed more than once", pr=num)
            continue
        snapshots[num] = snap

    # --- dependencies --------------------------------------------------------
    deps = doc.get("dependencies")
    if not isinstance(deps, list) or not deps:
        _hold(reasons, "MALFORMED", "dependencies must be a non-empty list")
        deps = []
    seen_deps: set[int] = set()
    dep_ok_shas: dict[int, set[str]] = {}
    for pos, dep in enumerate(deps):
        if not isinstance(dep, dict) or not _is_pr(dep.get("pr")):
            _hold(reasons, "MALFORMED", f"dependencies[{pos}] must have positive integer pr")
            continue
        num = dep["pr"]
        if num in seen_deps:
            _hold(reasons, "DUPLICATE_DEPENDENCY", f"dependency PR #{num} listed more than once", pr=num)
            continue
        seen_deps.add(num)
        if num == target_pr:
            _hold(reasons, "MALFORMED", f"target PR #{num} cannot depend on itself", pr=num)
            continue
        entry = {"pr": num, "provider": dep.get("provider"), "merged": False, "merge_commit_sha": None}
        deps_out.append(entry)
        snap = snapshots.get(num)
        if snap is None:
            _hold(reasons, "DEPENDENCY_SNAPSHOT_MISSING", f"no PR snapshot for dependency #{num}", pr=num)
            continue
        if snap.get("merged") is not True:
            _hold(reasons, "DEPENDENCY_NOT_MERGED", f"dependency PR #{num} is not merged", pr=num)
            continue
        merge_sha = snap.get("merge_commit_sha")
        if not _is_sha(merge_sha):
            _hold(reasons, "MALFORMED", f"dependency PR #{num} merged without 40-hex merge_commit_sha", pr=num)
            continue
        entry["merged"] = True
        entry["merge_commit_sha"] = merge_sha
        ok = {merge_sha}
        if _is_sha(snap.get("head_sha")):
            ok.add(snap["head_sha"])
        dep_ok_shas[num] = ok

    if target_pr is not None:
        tsnap = snapshots.get(target_pr)
        if tsnap is not None:
            if tsnap.get("merged") is True:
                _hold(reasons, "TARGET_ALREADY_MERGED", f"target PR #{target_pr} already merged", pr=target_pr)
            if tsnap.get("head_sha") is not None and tsnap.get("head_sha") != target_head:
                _hold(reasons, "STALE_TARGET_HEAD", "target head_sha differs from PR snapshot head", pr=target_pr)

    # --- integration run -------------------------------------------------------
    integ = doc.get("integration")
    integ_refs: dict[int, str] = {}
    if not isinstance(integ, dict):
        _hold(reasons, "INTEGRATION_MISSING", "no integration report")
    else:
        if not _is_sha(integ.get("base_sha")):
            _hold(reasons, "MALFORMED", "integration.base_sha must be 40-hex")
        refs = integ.get("refs")
        if not isinstance(refs, list):
            _hold(reasons, "MALFORMED", "integration.refs must be a list")
            refs = []
        for pos, ref in enumerate(refs):
            if not isinstance(ref, dict) or not _is_pr(ref.get("pr")) or not _is_sha(ref.get("sha")):
                _hold(reasons, "MALFORMED", f"integration.refs[{pos}] must have pr and 40-hex sha")
                continue
            num = ref["pr"]
            if num in integ_refs and integ_refs[num] != ref["sha"]:
                _hold(reasons, "CONFLICTING_INTEGRATION_REF", f"PR #{num} listed at two shas", pr=num)
                continue
            integ_refs[num] = ref["sha"]
        counts = {k: integ.get(k) for k in ("passed", "failed", "errors")}
        if not all(_is_count(v) for v in counts.values()):
            _hold(reasons, "MALFORMED", "integration passed/failed/errors must be non-negative integers")
        elif counts["failed"] or counts["errors"] or not counts["passed"]:
            _hold(
                reasons,
                "INTEGRATION_NOT_GREEN",
                f"integration passed={counts['passed']} failed={counts['failed']} errors={counts['errors']}",
            )
        for num, ok in sorted(dep_ok_shas.items()):
            sha = integ_refs.get(num)
            if sha is None:
                _hold(reasons, "INTEGRATION_REF_MISSING", f"integration did not include dependency #{num}", pr=num)
            elif sha not in ok:
                _hold(reasons, "STALE_DEPENDENCY_REF", f"integration used #{num} at a non-final sha", pr=num)
        if target_pr is not None:
            sha = integ_refs.get(target_pr)
            if sha is None:
                _hold(reasons, "INTEGRATION_REF_MISSING", f"integration did not include target #{target_pr}", pr=target_pr)
            elif sha != target_head:
                _hold(reasons, "STALE_TARGET_HEAD", "integration ran an older target head", pr=target_pr)

    # --- CI at target head ------------------------------------------------------
    ci = doc.get("ci")
    ci_out: dict[str, Any] = {"head_sha": None, "required": [], "missing_or_failed": []}
    if not isinstance(ci, dict):
        _hold(reasons, "CI_MISSING", "no CI evidence")
    else:
        ci_out["head_sha"] = ci.get("head_sha")
        if not _is_sha(ci.get("head_sha")):
            _hold(reasons, "MALFORMED", "ci.head_sha must be 40-hex")
        elif target_head is not None and ci["head_sha"] != target_head:
            _hold(reasons, "STALE_CI_HEAD", "CI evidence is for a different head than the target")
        required = ci.get("required_checks")
        checks = ci.get("checks")
        if (
            not isinstance(required, list)
            or not required
            or not all(isinstance(r, str) and r for r in required)
            or not isinstance(checks, list)
        ):
            _hold(reasons, "MALFORMED", "ci.required_checks must be non-empty strings and ci.checks a list")
        else:
            ci_out["required"] = sorted(set(required))
            results: dict[str, set[Any]] = {}
            for chk in checks:
                if isinstance(chk, dict) and isinstance(chk.get("name"), str):
                    results.setdefault(chk["name"], set()).add(chk.get("conclusion"))
            for name in ci_out["required"]:
                got = results.get(name)
                if got != {"success"}:
                    ci_out["missing_or_failed"].append(name)
                    detail = "missing" if not got else f"conclusions {sorted(map(str, got))}"
                    _hold(reasons, "CI_NOT_GREEN", f"required check {name!r} {detail}")

    reasons.sort(key=lambda r: (r["code"], r.get("pr", 0), r["detail"]))
    return {
        "schema": "provider_rollout_evidence_report_v1",
        "status": STATUS_HOLD if reasons else STATUS_COMPLETE,
        "target": {"pr": target_pr, "head_sha": target_head},
        "dependencies": sorted(deps_out, key=lambda d: d["pr"]),
        "integration_refs": {str(k): v for k, v in sorted(integ_refs.items())},
        "ci": ci_out,
        "hold_reasons": reasons,
        "evidence_limits": list(EVIDENCE_LIMITS),
        "merge_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, required=True, help="rollout evidence snapshot JSON")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        doc: Any = json.loads(args.snapshot.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        print(f"error: cannot read snapshot: {exc}", file=sys.stderr)
        return 2
    report = build_report(doc)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["status"] == STATUS_COMPLETE else 1


if __name__ == "__main__":
    raise SystemExit(main())
