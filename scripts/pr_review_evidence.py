"""Read-only exact-head PR review evidence collector (Issue #977 Phase A).

担当: ♦️ソラ

Collects, for one pull request event, deterministic evidence about:

* head provenance (event head vs. current PR head, base, run id/attempt),
* GitHub Actions workflow runs on the exact head (``actions:read``),
* submitted reviews (state + commit only; bodies are never stored),
* unresolved review threads (fixed read-only GraphQL query).

It never approves, merges, comments, dispatches or writes anything. The
overall verdict is deliberately *not* a PASS: the best possible outcome is
``EVIDENCE_COLLECTED``, which only means "no machine-visible blocker on the
exact head". Independent semantic review (❤️レイ / ⭐️ミナ) and the 🌙ルナ merge
gate remain required. Missing, failed, pending or stale inputs fail closed.

Coverage limits (reported in every output): third-party check suites and
legacy commit statuses are not read (they need ``checks:read`` /
``statuses:read``, outside the approved scope); COMMENTED reviews carry no
machine-verified verdict; reviewer identity is a GitHub login and cannot prove
team-member independence when several members share one account.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA_VERSION = 1
SELF_WORKFLOW_NAME = "PR Review Evidence (#977)"

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_LOGIN_RE = re.compile(r"^[A-Za-z0-9-]{1,39}(?:\[bot\])?$")
_STARTED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DECIMAL_RE = re.compile(r"^[0-9]{1,18}$")
_SAFE_TEXT_RE = re.compile(r"[^\w .:#()/\-\[\]]", re.UNICODE)

RUN_SUCCESS = {"success", "neutral", "skipped"}
RUN_FAILURE = {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"}

STATUS_LABELS_JA = {
    "EVIDENCE_COLLECTED": "機械的に確認できる阻害要因なし（承認ではありません）",
    "BLOCKED": "阻害要因あり",
    "PENDING": "CI実行中・未完了",
    "STALE": "イベント時のHEADが古い",
    "UNKNOWN": "証跡を取得・判定できません",
}


class EvidenceUnavailable(RuntimeError):
    """An input could not be read; the dependent section must be UNKNOWN."""


def _safe_text(value: Any, limit: int = 120) -> str:
    text = _SAFE_TEXT_RE.sub("_", str(value))
    return text[:limit]


def _utc_timestamp(value: Any) -> str | None:
    """Strict UTC ``YYYY-MM-DDTHH:MM:SSZ`` that is also a real calendar instant."""
    if not isinstance(value, str) or not _STARTED_RE.fullmatch(value):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return value


def _sha(value: Any) -> str | None:
    return value if isinstance(value, str) and _SHA_RE.fullmatch(value) else None


def _login(value: Any) -> str | None:
    return value if isinstance(value, str) and _LOGIN_RE.fullmatch(value) else None


# --------------------------------------------------------------------------
# Pure classifiers (no I/O). Every malformed input yields UNKNOWN, never PASS.
# --------------------------------------------------------------------------


def classify_head(event_head: Any, current_head: Any, head_after: Any = None) -> dict[str, Any]:
    """CURRENT only if the event head equals the PR head read both before and
    after all other evidence was collected (no head change mid-collection)."""
    event_sha, current_sha, after_sha = _sha(event_head), _sha(current_head), _sha(head_after)
    if event_sha is None or current_sha is None or after_sha is None:
        status = "UNKNOWN"
    elif event_sha != current_sha or current_sha != after_sha:
        status = "STALE"
    else:
        status = "CURRENT"
    return {
        "status": status,
        "event_head_sha": event_sha,
        "current_head_sha": current_sha,
        "head_sha_after_collection": after_sha,
    }


def classify_ci(runs: Any, *, head_sha: str | None, self_run_id: int | None) -> dict[str, Any]:
    """Classify GitHub Actions workflow runs observed for the exact head.

    The runs API lists each run once, with ``run_attempt`` already set to that
    run's latest attempt. When a workflow has several distinct runs on the same
    head (e.g. reopened, or a re-run of an older run), the one whose latest
    attempt started last wins: ``run_started_at`` first, then run id and attempt
    as tie-breakers. Attempt numbers are never compared across different runs.
    This workflow's own runs are excluded so it can never vouch for itself.
    """
    if runs is None or not isinstance(runs, list) or head_sha is None:
        return {"status": "UNKNOWN", "observed": [], "reason": "workflow runs unavailable"}
    latest: dict[str, dict[str, Any]] = {}
    malformed = 0
    for run in runs:
        if not isinstance(run, dict):
            malformed += 1
            continue
        run_id = run.get("id")
        name = run.get("name")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or not isinstance(name, str):
            malformed += 1
            continue
        if run_id == self_run_id or name == SELF_WORKFLOW_NAME:
            continue
        if run.get("head_sha") != head_sha:
            continue  # evidence for another commit is never reused
        attempt = run.get("run_attempt") if isinstance(run.get("run_attempt"), int) else 0
        started = _utc_timestamp(run.get("run_started_at")) or ""
        order = (started, run_id, attempt)
        previous = latest.get(name)
        if previous is None or order > previous["_order"]:
            latest[name] = {
                "_order": order,
                "id": run_id,
                "attempt": attempt,
                "name": _safe_text(name),
                "status": _safe_text(run.get("status") or "unknown", 30),
                "conclusion": _safe_text(run.get("conclusion") or "", 30) or None,
                "event": _safe_text(run.get("event") or "", 30) or None,
            }
    observed = sorted(
        ({k: v for k, v in item.items() if k != "_order"} for item in latest.values()),
        key=lambda item: item["name"],
    )
    if malformed:
        return {"status": "UNKNOWN", "observed": observed, "reason": f"{malformed} malformed run record(s)"}
    if not observed:
        return {"status": "UNKNOWN", "observed": [], "reason": "no workflow run observed on exact head"}
    if any(item["status"] == "completed" and item["conclusion"] in RUN_FAILURE for item in observed):
        status, reason = "FAILED", "a workflow run failed on exact head"
    elif any(item["status"] != "completed" for item in observed):
        status, reason = "PENDING", "a workflow run is not completed"
    elif all(item["conclusion"] in RUN_SUCCESS for item in observed):
        status, reason = "SUCCESS", None
    else:
        status, reason = "UNKNOWN", "unrecognised workflow conclusion"
    return {"status": status, "observed": observed, "reason": reason}


def classify_reviews(reviews: Any, *, head_sha: str | None) -> dict[str, Any]:
    """Summarise reviews without bodies. COMMENTED is never counted as approval."""
    if reviews is None or not isinstance(reviews, list) or head_sha is None:
        return {"status": "UNKNOWN", "reason": "reviews unavailable", "entries": []}
    entries: list[dict[str, Any]] = []
    malformed = 0
    for index, review in enumerate(reviews):
        if not isinstance(review, dict):
            malformed += 1
            continue
        state = review.get("state")
        if not isinstance(state, str) or state not in REVIEW_STATES:
            malformed += 1
            continue
        if state == "PENDING":
            continue  # unsubmitted draft reviews are not evidence
        user = review.get("user") if isinstance(review.get("user"), dict) else {}
        login = _login(user.get("login"))
        commit = _sha(review.get("commit_id"))
        submitted = _utc_timestamp(review.get("submitted_at"))
        # Every submitted review must name a valid commit and a strict UTC
        # timestamp; otherwise it can neither be placed in time nor bound to a
        # head, and must not be able to supersede an earlier CHANGES_REQUESTED.
        if login is None or commit is None or submitted is None:
            malformed += 1
            continue
        entries.append({
            "reviewer": login,
            "state": state,
            "commit_id": commit,
            "exact_head": commit == head_sha,
            "submitted_at": submitted,
            "_index": index,
        })
    # Chronological order by submitted_at (API order only breaks exact ties).
    entries.sort(key=lambda entry: (entry["submitted_at"], entry["_index"]))
    for entry in entries:
        del entry["_index"]
    # Latest decisive state per reviewer (APPROVED / CHANGES_REQUESTED / DISMISSED).
    decisive: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            decisive[entry["reviewer"]] = entry
    outstanding_changes = sorted(r for r, e in decisive.items() if e["state"] == "CHANGES_REQUESTED")
    approved_on_head = sorted(
        r for r, e in decisive.items() if e["state"] == "APPROVED" and e["exact_head"]
    )
    commented_on_head = sum(1 for e in entries if e["state"] == "COMMENTED" and e["exact_head"])
    stale = sum(1 for e in entries if not e["exact_head"])
    if outstanding_changes:
        # A known blocker stays a blocker even if other records are malformed.
        status, reason = "CHANGES_REQUESTED", "GitHub CHANGES_REQUESTED is outstanding"
        if malformed:
            reason += f"; {malformed} malformed review record(s)"
    elif malformed:
        status, reason = "UNKNOWN", f"{malformed} malformed review record(s)"
    elif not any(e["exact_head"] for e in entries):
        status, reason = "NO_EXACT_HEAD_REVIEW", "no submitted review on exact head"
    else:
        status, reason = "REVIEWS_PRESENT", None
    return {
        "status": status,
        "reason": reason,
        "approved_on_exact_head": approved_on_head,
        "commented_on_exact_head": commented_on_head,
        "outstanding_changes_requested": outstanding_changes,
        "stale_review_count": stale,
        "entries": entries,
        "note": "COMMENTED reviews carry no machine-verified verdict; not equivalent to APPROVED.",
    }


def classify_threads(threads: Any) -> dict[str, Any]:
    if threads is None or not isinstance(threads, list):
        return {"status": "UNKNOWN", "unresolved": None, "total": None}
    flags = []
    for thread in threads:
        if not isinstance(thread, dict) or not isinstance(thread.get("isResolved"), bool):
            return {"status": "UNKNOWN", "unresolved": None, "total": None}
        flags.append(thread["isResolved"])
    unresolved = sum(1 for resolved in flags if not resolved)
    return {
        "status": "UNRESOLVED" if unresolved else "NONE_UNRESOLVED",
        "unresolved": unresolved,
        "total": len(flags),
    }


def overall_status(head: dict, ci: dict, reviews: dict, threads: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if head["status"] == "STALE":
        return "STALE", ["event head differs from current PR head"]
    if ci["status"] == "FAILED":
        reasons.append("CI failed on exact head")
    if reviews["status"] == "CHANGES_REQUESTED":
        reasons.append("GitHub CHANGES_REQUESTED outstanding")
    if threads["status"] == "UNRESOLVED":
        reasons.append(f"{threads['unresolved']} unresolved review thread(s)")
    if reasons:
        return "BLOCKED", reasons
    unknown = [
        name for name, section in (("head", head), ("ci", ci), ("reviews", reviews), ("threads", threads))
        if section["status"] == "UNKNOWN"
    ]
    if unknown:
        return "UNKNOWN", [f"{name} evidence unavailable" for name in unknown]
    if ci["status"] == "PENDING":
        return "PENDING", ["CI not completed on exact head"]
    if reviews["status"] == "NO_EXACT_HEAD_REVIEW":
        return "UNKNOWN", ["no submitted review on exact head"]
    return "EVIDENCE_COLLECTED", []


def build_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build the evidence report from an already-collected snapshot (pure)."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    pr = snapshot.get("pull_request") if isinstance(snapshot.get("pull_request"), dict) else {}
    head = classify_head(snapshot.get("event_head_sha"), pr.get("head_sha"), pr.get("head_sha_after"))
    exact = head["event_head_sha"] if head["status"] == "CURRENT" else None
    self_run_id = snapshot.get("run_id") if isinstance(snapshot.get("run_id"), int) else None
    ci = classify_ci(snapshot.get("workflow_runs"), head_sha=exact, self_run_id=self_run_id)
    reviews = classify_reviews(snapshot.get("reviews"), head_sha=exact)
    threads = classify_threads(snapshot.get("review_threads"))
    status, reasons = overall_status(head, ci, reviews, threads)
    number = pr.get("number") if isinstance(pr.get("number"), int) else None
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "status_ja": STATUS_LABELS_JA[status],
        "reasons": reasons,
        "is_approval": False,
        "provenance": {
            "repository": _safe_text(snapshot.get("repository") or "", 100) or None,
            "pull_request": number,
            "event_name": _safe_text(snapshot.get("event_name") or "", 40) or None,
            "event_action": _safe_text(snapshot.get("event_action") or "", 40) or None,
            "event_head_sha": head["event_head_sha"],
            "current_head_sha": head["current_head_sha"],
            "base_sha": _sha(pr.get("base_sha")),
            "draft": pr.get("draft") if isinstance(pr.get("draft"), bool) else None,
            "run_id": self_run_id,
            "run_attempt": snapshot.get("run_attempt") if isinstance(snapshot.get("run_attempt"), int) else None,
            "collected_at": _safe_text(snapshot.get("collected_at") or "", 40) or None,
        },
        "head": head,
        "ci": ci,
        "reviews": reviews,
        "review_threads": threads,
        "collection_errors": [
            _safe_text(e, 160) for e in (snapshot.get("errors") if isinstance(snapshot.get("errors"), list) else [])
        ],
        "coverage": {
            "github_actions_runs": True,
            "third_party_check_suites": False,
            "legacy_commit_statuses": False,
            "review_bodies_stored": False,
            "independent_review_verified": False,
            "ux_verified": False,
        },
    }


SECTION_LABELS_JA = {
    "CURRENT": "最新",
    "STALE": "古い",
    "UNKNOWN": "未確認",
    "SUCCESS": "成功",
    "PENDING": "実行中",
    "FAILED": "失敗",
    "CHANGES_REQUESTED": "変更要求あり",
    "NO_EXACT_HEAD_REVIEW": "最新HEADへのレビューなし",
    "REVIEWS_PRESENT": "レビューあり",
    "UNRESOLVED": "未解決あり",
    "NONE_UNRESOLVED": "未解決なし",
}

REASON_LABELS_JA = {
    "event head differs from current PR head": "イベント時のHEADが現在のPRのHEADと異なる",
    "CI failed on exact head": "最新HEADでCIが失敗している",
    "GitHub CHANGES_REQUESTED outstanding": "GitHub上の変更要求（CHANGES_REQUESTED）が残っている",
    "CI not completed on exact head": "最新HEADのCIが完了していない",
    "no submitted review on exact head": "最新HEADへの提出済みレビューがない",
    "head evidence unavailable": "HEADの情報を取得できない",
    "ci evidence unavailable": "CIの情報を取得できない",
    "reviews evidence unavailable": "レビューの情報を取得できない",
    "threads evidence unavailable": "レビュースレッドの情報を取得できない",
}

NEXT_ACTION_JA = {
    "EVIDENCE_COLLECTED": "❤️レイ / ⭐️ミナ の独立レビュー → 🌙ルナ のGate（このレポートは承認ではありません）",
    "PENDING": "CIの完了後に、Actionsの結果と最新の run を確認する（このレポートはイベント時点のスナップショット）",
    "BLOCKED": "実装担当が「理由」の阻害要因を解消し、新しいHEADで再確認する",
    "STALE": "現在のHEADで実行された最新の run のレポートを確認する",
    "UNKNOWN": "取得できなかった証跡を、Job log・PR画面で手動確認する（権限・API失敗の可能性）",
}


def _label(value: Any) -> str:
    text = str(value)
    ja = SECTION_LABELS_JA.get(text)
    return f"{ja}（{text}）" if ja else text


def _reason_ja(reason: str) -> str:
    if reason in REASON_LABELS_JA:
        return f"{REASON_LABELS_JA[reason]}（{reason}）"
    match = re.fullmatch(r"(\d+) unresolved review thread\(s\)", reason)
    if match:
        return f"未解決のレビュースレッドが{match.group(1)}件ある（{reason}）"
    return reason


def render_summary_ja(report: dict[str, Any]) -> str:
    prov = report["provenance"]
    ci, reviews, threads = report["ci"], report["reviews"], report["review_threads"]
    reviews_known = reviews["status"] != "UNKNOWN"

    def count(value: Any) -> str:
        # An unavailable inventory is "未確認", never a measured zero.
        return f"{value}件" if reviews_known else "未確認"

    lines = [
        f"## PRレビュー証跡（#977 Phase A）: {report['status']}",
        "",
        f"**判定: {report['status_ja']}**",
        "",
        "> これは機械的に集めた証跡です。承認・merge可否・UX・AIによる独立レビューを示すものではありません。"
        "❤️レイ / ⭐️ミナ の独立レビューと 🌙ルナ のGateは別途必要です。",
        "",
        f"**次に確認すること:** {NEXT_ACTION_JA[report['status']]}",
        "",
        f"- PR: #{prov['pull_request']} / イベント: {prov['event_name']} ({prov['event_action']})",
        f"- イベント時HEAD: `{prov['event_head_sha']}` / 現在のHEAD: `{prov['current_head_sha']}`"
        f"（{_label(report['head']['status'])}）",
        f"- base: `{prov['base_sha']}` / run: {prov['run_id']} (attempt {prov['run_attempt']})",
        f"- CI（GitHub Actions、exact head）: {_label(ci['status'])}"
        + (f" — {ci['reason']}" if ci.get("reason") else ""),
    ]
    for item in ci["observed"]:
        lines.append(f"  - {item['name']}: {item['status']} / {item['conclusion']}")
    lines += [
        f"- レビュー: {_label(reviews['status'])}"
        + (f" — {reviews['reason']}" if reviews.get("reason") else ""),
        f"  - exact headでのAPPROVED: {count(len(reviews.get('approved_on_exact_head') or []))} / "
        f"COMMENTED: {count(reviews.get('commented_on_exact_head', 0))}（COMMENTEDは承認ではありません） / "
        f"古いHEADへのレビュー: {count(reviews.get('stale_review_count', 0))}",
        f"- 未解決のレビュースレッド: "
        + (f"{threads['unresolved']}件" if threads['unresolved'] is not None else "未確認（UNKNOWN）"),
    ]
    if report["reasons"]:
        lines += ["", "**理由**"] + [f"- {_reason_ja(reason)}" for reason in report["reasons"]]
    lines += [
        "",
        "**対象外**: 外部のcheck suite・旧commit status・レビュー本文の内容・レビュアーが別人であることの確認・実画面のUX。",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Read-only collection (GET + one fixed GraphQL query). No caller URLs.
# --------------------------------------------------------------------------

THREADS_QUERY = (
    "query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name)"
    "{pullRequest(number:$number){reviewThreads(first:100){totalCount nodes{isResolved}}}}}"
)


class ReadOnlyClient:
    def __init__(self, repository: str, token: str):
        if not _REPO_RE.fullmatch(repository):
            raise ValueError("invalid repository")
        if not token:
            raise EvidenceUnavailable("missing read token")
        self.repository = repository
        self.token = token

    def _request(self, url: str, *, data: bytes | None = None) -> Any:
        req = Request(url, data=data, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sado-issue977-readonly",
            **({"Content-Type": "application/json"} if data is not None else {}),
        }, method="POST" if data is not None else "GET")
        try:
            with urlopen(req, timeout=15) as response:
                body = response.read(5_000_001)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise EvidenceUnavailable(f"read failed ({type(exc).__name__})") from None
        if len(body) > 5_000_000:
            raise EvidenceUnavailable("oversized API response")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise EvidenceUnavailable("invalid JSON response") from None

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        allowed = (
            re.fullmatch(r"pulls/[1-9][0-9]*", endpoint)
            or re.fullmatch(r"pulls/[1-9][0-9]*/reviews", endpoint)
            or endpoint == "actions/runs"
        )
        if not allowed:
            raise ValueError("endpoint not allowlisted")
        query = f"?{urlencode(params)}" if params else ""
        return self._request(f"https://api.github.com/repos/{self.repository}/{endpoint}{query}")

    def review_threads(self, number: int) -> list[dict[str, Any]]:
        owner, name = self.repository.split("/", 1)
        payload = json.dumps({"query": THREADS_QUERY, "variables": {"owner": owner, "name": name, "number": number}})
        data = self._request("https://api.github.com/graphql", data=payload.encode())
        try:
            threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]
            nodes, total = threads["nodes"], threads["totalCount"]
        except (KeyError, TypeError):
            raise EvidenceUnavailable("review threads unavailable") from None
        if not isinstance(nodes, list) or not isinstance(total, int) or total != len(nodes):
            raise EvidenceUnavailable("review thread inventory incomplete")
        return nodes


def collect_snapshot(event: dict[str, Any], client: ReadOnlyClient, *, run_id: int | None,
                     run_attempt: int | None, event_name: str) -> dict[str, Any]:
    pr_event = event.get("pull_request") if isinstance(event.get("pull_request"), dict) else {}
    number = pr_event.get("number")
    head = pr_event.get("head") if isinstance(pr_event.get("head"), dict) else {}
    snapshot: dict[str, Any] = {
        "repository": client.repository,
        "event_name": event_name,
        "event_action": event.get("action"),
        "event_head_sha": head.get("sha"),
        "run_id": run_id,
        "run_attempt": run_attempt,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pull_request": {"number": number if isinstance(number, int) else None},
        "workflow_runs": None,
        "reviews": None,
        "review_threads": None,
        "errors": [],
    }
    if not isinstance(number, int) or number < 1:
        snapshot["errors"].append("event has no pull request number")
        return snapshot
    try:
        pr = client.get(f"pulls/{number}")
        if isinstance(pr, dict):
            snapshot["pull_request"].update({
                "head_sha": (pr.get("head") or {}).get("sha") if isinstance(pr.get("head"), dict) else None,
                "base_sha": (pr.get("base") or {}).get("sha") if isinstance(pr.get("base"), dict) else None,
                "draft": pr.get("draft"),
            })
    except EvidenceUnavailable as exc:
        snapshot["errors"].append(f"pull request: {exc}")
    head_sha = _sha(head.get("sha"))
    if head_sha:
        try:
            runs = client.get("actions/runs", {"head_sha": head_sha, "per_page": 100})
            items = runs.get("workflow_runs") if isinstance(runs, dict) else None
            total = runs.get("total_count") if isinstance(runs, dict) else None
            if (isinstance(items, list) and isinstance(total, int) and not isinstance(total, bool)
                    and total >= 0 and total == len(items)):
                snapshot["workflow_runs"] = items
            else:
                snapshot["errors"].append("workflow runs: incomplete inventory")
        except EvidenceUnavailable as exc:
            snapshot["errors"].append(f"workflow runs: {exc}")
    try:
        reviews = client.get(f"pulls/{number}/reviews", {"per_page": 100})
        # This endpoint has no total_count. A full page (100) may be truncated,
        # so it is deliberately rejected as an incomplete inventory (UNKNOWN).
        if isinstance(reviews, list) and len(reviews) < 100:
            snapshot["reviews"] = reviews
        else:
            snapshot["errors"].append("reviews: incomplete inventory")
    except EvidenceUnavailable as exc:
        snapshot["errors"].append(f"reviews: {exc}")
    try:
        snapshot["review_threads"] = client.review_threads(number)
    except EvidenceUnavailable as exc:
        snapshot["errors"].append(f"review threads: {exc}")
    # Re-read the PR head after every other read: if it moved mid-collection,
    # the evidence is reported as STALE instead of CURRENT.
    try:
        pr_after = client.get(f"pulls/{number}")
        head_after = pr_after.get("head") if isinstance(pr_after, dict) else None
        snapshot["pull_request"]["head_sha_after"] = head_after.get("sha") if isinstance(head_after, dict) else None
    except EvidenceUnavailable as exc:
        snapshot["errors"].append(f"pull request re-read: {exc}")
    return snapshot


def _int_env(name: str) -> int | None:
    value = os.environ.get(name, "")
    return int(value) if _DECIMAL_RE.fullmatch(value) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only PR review evidence (#977 Phase A)")
    parser.add_argument("--snapshot", type=Path, help="offline mode: classify a saved snapshot JSON")
    parser.add_argument("--output", type=Path, default=Path("pr-review-evidence.json"))
    parser.add_argument("--summary", type=Path, default=Path("pr-review-evidence.md"))
    args = parser.parse_args(argv)

    try:
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        else:
            event_path = os.environ.get("GITHUB_EVENT_PATH", "")
            event = json.loads(Path(event_path).read_text(encoding="utf-8")) if event_path else {}
            client = ReadOnlyClient(os.environ.get("GITHUB_REPOSITORY", ""),
                                    os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))
            snapshot = collect_snapshot(
                event if isinstance(event, dict) else {}, client,
                run_id=_int_env("GITHUB_RUN_ID"), run_attempt=_int_env("GITHUB_RUN_ATTEMPT"),
                event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
            )
    except (OSError, ValueError, UnicodeDecodeError, EvidenceUnavailable) as exc:
        snapshot = {"errors": [f"collection failed ({type(exc).__name__})"]}

    try:
        report = build_report(snapshot)
    except Exception as exc:  # noqa: BLE001 - always emit a fail-closed report
        report = build_report({"errors": [f"classification failed ({type(exc).__name__})"]})
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.summary.write_text(render_summary_ja(report), encoding="utf-8")
    print(f"PR review evidence: {report['status']}")
    # Non-blocking by design: the verdict lives in the artifact, not the exit code.
    return 0


if __name__ == "__main__":
    sys.exit(main())
