"""Mobile browser audit verdict contract (#998, #950 Phase B).

担当: ♦️ソラ

Pure judgement over *already captured* browser observations (e.g. a future
Playwright run at 320/390 CSS px). This module never launches a browser,
fetches a URL or touches a workflow. Contract follows ⭐️ミナ's Phase B spec
(#977 comment 7239385669):

* horizontal overflow: documentElement/body ``scrollWidth <= clientWidth + 1``;
  elements that scroll inside their own container are noted, not page overflow;
* anchors: the visible link must reach an existing, visible target;
* details: content hidden while closed and visible once opened;
* nothing to inspect -> NOT_APPLICABLE with a reason;
* missing observation -> NOT_RUN; timeout / JS error / malformed -> UNKNOWN;
* an audit where nothing was actually checked can never be PASS.

A PASS here means only "the supplied observations satisfy the rules"; it is
not a real-browser PASS unless the observations came from one, and it is not
semantic UX review (30-second comprehension, Japanese naturalness).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_VIEWPORTS = (320, 390)
MANDATORY_VIEWPORTS = (320, 390)  # always audited, whatever the manifest says
CLIENT_WIDTH_TOLERANCE = 24  # scrollbars may narrow clientWidth below the viewport
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEVERITY = {"route_presence": "P0", "horizontal_overflow": "P1", "anchor": "P1", "details": "P2", "provenance": "P1"}
RANK = {"FAIL": 4, "UNKNOWN": 3, "NOT_RUN": 2, "PASS": 1, "NOT_APPLICABLE": 0}

STATUS_JA = {
    "PASS": "合格（与えられた観測の範囲）",
    "FAIL": "不合格",
    "UNKNOWN": "判定不能",
    "NOT_RUN": "未実施",
    "NOT_APPLICABLE": "対象なし",
}


def _int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _diag(value: Any) -> Any:
    """Bounded, JSON-safe echo of an untrusted value for diagnostics."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:200]
    return f"<{type(value).__name__}>"


def _finding(route: str, viewport: Any, rule: str, status: str, observed: Any, expected: str,
             screenshot: Any = None, reason: str | None = None) -> dict[str, Any]:
    return {
        "route": route,
        "viewport": viewport,
        "rule": rule,
        "severity": SEVERITY[rule],
        "status": status,
        "observed": observed,
        "expected": expected,
        "screenshot": screenshot if isinstance(screenshot, str) else None,
        "reason": reason,
    }


def _overflow(route: str, vp: int, obs: dict[str, Any], shot: Any) -> dict[str, Any]:
    keys = ("document_scroll_width", "document_client_width", "body_scroll_width", "body_client_width")
    values = {key: obs.get(key) for key in keys}
    expected = "documentElement/body scrollWidth <= clientWidth + 1"
    if not all(_int(v) and v >= 0 for v in values.values()):
        return _finding(route, vp, "horizontal_overflow", "UNKNOWN", {k: _diag(v) for k, v in values.items()},
                        expected, shot, "width measurement missing or malformed")
    client = values["document_client_width"]
    if values["document_client_width"] <= 0 or values["body_client_width"] <= 0 \
            or not (vp - CLIENT_WIDTH_TOLERANCE <= client <= vp):
        return _finding(route, vp, "horizontal_overflow", "UNKNOWN", values, expected, shot,
                        f"client width {client} not consistent with a {vp}px viewport (no real measurement)")
    elements = obs.get("overflow_elements", [])
    if not isinstance(elements, list) or not all(isinstance(e, dict) and isinstance(e.get("selector"), str) for e in elements):
        return _finding(route, vp, "horizontal_overflow", "UNKNOWN", values, expected, shot, "overflow element list malformed")
    page_overflow = (values["document_scroll_width"] > values["document_client_width"] + 1
                     or values["body_scroll_width"] > values["body_client_width"] + 1)
    local = [e["selector"][:120] for e in elements if e.get("scrollable_container") is True]
    offenders = [e["selector"][:120] for e in elements if e.get("scrollable_container") is not True]
    observed = {**values, "page_overflow_elements": offenders, "locally_scrollable": local}
    if page_overflow:
        return _finding(route, vp, "horizontal_overflow", "FAIL", observed, expected, shot,
                        "page-level horizontal overflow")
    return _finding(route, vp, "horizontal_overflow", "PASS", observed, expected, shot,
                    "locally scrollable elements only" if local else None)


def _anchors(route: str, vp: int, obs: dict[str, Any], shot: Any) -> list[dict[str, Any]]:
    anchors = obs.get("anchors")
    expected = "visible link reaches an existing, visible target"
    if anchors is None:
        return [_finding(route, vp, "anchor", "UNKNOWN", None, expected, shot, "anchor inspection not recorded")]
    if not isinstance(anchors, list):
        return [_finding(route, vp, "anchor", "UNKNOWN", None, expected, shot, "anchor list malformed")]
    if not anchors:
        return [_finding(route, vp, "anchor", "NOT_APPLICABLE", [], expected, shot, "no in-page anchors to inspect")]
    out = []
    for anchor in anchors:
        if not isinstance(anchor, dict) or not isinstance(anchor.get("href"), str):
            out.append(_finding(route, vp, "anchor", "UNKNOWN", None, expected, shot, "anchor record malformed"))
            continue
        flags = {k: anchor.get(k) for k in ("link_visible", "target_exists", "target_visible", "reached")}
        observed = {"href": anchor["href"][:200], **{k: _diag(v) for k, v in flags.items()}}
        known_false = [k for k, v in flags.items() if v is False]
        if known_false:
            # A measured contradiction is a FAIL even if other flags are missing.
            out.append(_finding(route, vp, "anchor", "FAIL", observed, expected, shot, "failed: " + ", ".join(known_false)))
        elif any(not isinstance(v, bool) for v in flags.values()):
            out.append(_finding(route, vp, "anchor", "UNKNOWN", observed, expected, shot, "anchor flags not measured"))
        else:
            out.append(_finding(route, vp, "anchor", "PASS", observed, expected, shot))
    return out


def _details(route: str, vp: int, obs: dict[str, Any], shot: Any) -> list[dict[str, Any]]:
    details = obs.get("details")
    expected = "content hidden while closed and visible after opening"
    if details is None:
        return [_finding(route, vp, "details", "UNKNOWN", None, expected, shot, "details inspection not recorded")]
    if not isinstance(details, list):
        return [_finding(route, vp, "details", "UNKNOWN", None, expected, shot, "details list malformed")]
    if not details:
        return [_finding(route, vp, "details", "NOT_APPLICABLE", [], expected, shot, "no <details> elements")]
    out = []
    for item in details:
        if not isinstance(item, dict) or not isinstance(item.get("selector"), str):
            out.append(_finding(route, vp, "details", "UNKNOWN", None, expected, shot, "details record malformed"))
            continue
        closed, opened = item.get("content_visible_closed"), item.get("content_visible_open")
        observed = {"selector": item["selector"][:120], "content_visible_closed": _diag(closed),
                    "content_visible_open": _diag(opened)}
        if not isinstance(closed, bool) or not isinstance(opened, bool):
            out.append(_finding(route, vp, "details", "UNKNOWN", observed, expected, shot, "visibility not measured"))
        elif opened and not closed:
            out.append(_finding(route, vp, "details", "PASS", observed, expected, shot))
        else:
            out.append(_finding(route, vp, "details", "FAIL", observed, expected, shot,
                                "content not visible after opening" if not opened else "content visible while closed"))
    return out


def evaluate(audit: Any) -> dict[str, Any]:
    """Judge captured observations. No browser, network or filesystem access."""
    audit = audit if isinstance(audit, dict) else {}
    findings: list[dict[str, Any]] = []

    source, artifact, run_id = audit.get("source_sha"), audit.get("artifact_sha"), audit.get("run_id")
    provenance_ok = (isinstance(source, str) and bool(_SHA_RE.fullmatch(source))
                     and isinstance(artifact, str) and bool(_SHA_RE.fullmatch(artifact))
                     and _int(run_id) and run_id > 0)
    findings.append(_finding("*", None, "provenance", "PASS" if provenance_ok else "UNKNOWN",
                             {"source_sha": _diag(source), "artifact_sha": _diag(artifact), "run_id": _diag(run_id)},
                             "40-hex source/artifact SHA and positive run id",
                             reason=None if provenance_ok else "provenance missing or malformed"))

    routes = audit.get("required_routes")
    supplied = audit.get("viewports", list(DEFAULT_VIEWPORTS))
    if (not isinstance(routes, list) or not routes or not all(isinstance(r, str) and r.startswith("/") for r in routes)
            or not isinstance(supplied, list) or not supplied or not all(_int(v) and v > 0 for v in supplied)):
        findings.append(_finding("*", None, "route_presence", "UNKNOWN",
                                 {"required_routes": _diag(routes), "viewports": _diag(supplied)},
                                 "non-empty route manifest and viewport list", reason="route manifest or viewports malformed"))
        return _report(audit, findings, observed_rows=0)
    missing_mandatory = [v for v in MANDATORY_VIEWPORTS if v not in supplied]
    if missing_mandatory:
        findings.append(_finding("*", None, "route_presence", "UNKNOWN", {"viewports": supplied},
                                 f"mandatory viewports {list(MANDATORY_VIEWPORTS)} audited",
                                 reason=f"manifest omits mandatory viewport(s) {missing_mandatory}; audit is partial"))
    viewports = sorted(set(supplied) | set(MANDATORY_VIEWPORTS))

    observations = audit.get("observations")
    index: dict[tuple[str, int], Any] = {}
    duplicates = set()
    malformed_rows = 0
    if observations is not None and not isinstance(observations, list):
        malformed_rows += 1
    for obs in observations if isinstance(observations, list) else []:
        if isinstance(obs, dict) and isinstance(obs.get("route"), str) and _int(obs.get("viewport")):
            key = (obs["route"], obs["viewport"])
            if key in index:
                duplicates.add(key)
            index[key] = obs
        else:
            malformed_rows += 1
    if malformed_rows:
        findings.append(_finding("*", None, "route_presence", "UNKNOWN", {"malformed_rows": malformed_rows},
                                 "every observation row has a route and integer viewport",
                                 reason="malformed observation row(s); results may be ambiguous"))

    for route in routes:
        for vp in viewports:
            obs = index.get((route, vp))
            expected = "route renders (status OK)"
            if (route, vp) in duplicates:
                findings.append(_finding(route, vp, "route_presence", "UNKNOWN", None, expected,
                                         reason="duplicate observations for route/viewport"))
                continue
            if obs is None:
                findings.append(_finding(route, vp, "route_presence", "NOT_RUN", None, expected,
                                         reason="no observation captured"))
                continue
            shot = obs.get("screenshot")
            status = obs.get("status")
            if status == "NOT_FOUND":
                findings.append(_finding(route, vp, "route_presence", "FAIL", status, expected, shot, "required route missing"))
                continue
            if status != "OK":
                findings.append(_finding(route, vp, "route_presence", "UNKNOWN", status, expected, shot,
                                         "timeout, JS error or unrecognised status"))
                continue
            findings.append(_finding(route, vp, "route_presence", "PASS", status, expected, shot))
            findings.append(_overflow(route, vp, obs, shot))
            findings.extend(_anchors(route, vp, obs, shot))
            findings.extend(_details(route, vp, obs, shot))
    return _report(audit, findings, observed_rows=len(index), provenance_ok=provenance_ok)


def _report(audit: dict[str, Any], findings: list[dict[str, Any]], *, observed_rows: int,
            provenance_ok: bool = False) -> dict[str, Any]:
    checked = [f for f in findings if f["rule"] != "provenance" and f["status"] in {"PASS", "FAIL"}]
    # NOT_APPLICABLE has the lowest rank, so it never decides the verdict on
    # its own; the worst remaining status does.
    worst = max((RANK[f["status"]] for f in findings), default=RANK["NOT_RUN"])
    verdict = next(status for status, rank in RANK.items() if rank == worst)
    if verdict in {"PASS", "NOT_APPLICABLE"} and not checked:
        verdict = "NOT_RUN"  # nothing was actually checked: never PASS
    counts = {status: sum(1 for f in findings if f["status"] == status) for status in RANK}
    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "verdict_ja": STATUS_JA[verdict],
        "counts": counts,
        "findings": findings,
        "coverage": {
            # A caller's claim alone is not verification: it counts only with
            # valid provenance and at least one actual observation row.
            "caller_claims_browser_capture": audit.get("captured_by") == "browser",
            "observations_from_real_browser": (audit.get("captured_by") == "browser" and provenance_ok
                                               and observed_rows > 0),
            "semantic_ux_review": False,
            "public_http_verified": False,
        },
        "limits": [
            "judges supplied observations only; launches no browser and fetches no URL",
            "not semantic UX review (30-second comprehension, Japanese naturalness)",
        ],
    }


def render_summary_ja(report: dict[str, Any]) -> str:
    lines = [f"## モバイルブラウザ監査（#998）: {report['verdict']}", "", f"**判定: {report['verdict_ja']}**", ""]
    lines.append("> 与えられた観測データに対する判定です。意味的なUXレビュー（30秒で理解できるか・日本語の自然さ）は含みません。")
    lines.append("")
    for f in report["findings"]:
        if f["status"] in {"FAIL", "UNKNOWN", "NOT_RUN"}:
            where = f"{f['route']} @ {f['viewport']}px" if f["viewport"] is not None else "全体"
            lines.append(f"- [{f['severity']}] {where} {f['rule']}: "
                         f"{STATUS_JA[f['status']]}（{f['status']}）" + (f" — {f['reason']}" if f.get("reason") else ""))
    if lines[-1] == "":
        lines.append("- 問題として報告する項目はありません。")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mobile browser audit verdict contract (#998)")
    parser.add_argument("observations", help="captured observation JSON file")
    parser.add_argument("--output")
    parser.add_argument("--summary")
    args = parser.parse_args(argv)
    try:
        with open(args.observations, encoding="utf-8") as handle:
            audit = json.load(handle)
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        audit = None
    report = evaluate(audit)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as handle:
            handle.write(render_summary_ja(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
