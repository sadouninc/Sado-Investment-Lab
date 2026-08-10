#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ACTORS = {"SORA", "NAGI", "LUNA"}
QUALITY_GATES = {"GREEN", "PENDING", "BLOCKED"}
WAIT_REASONS = {"BLOCKED", "NO_SAFE_WORK", "OWNER_WAIT", "NOT_APPLICABLE"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    required = {
        "actor", "run_at", "advanced_items", "prs_opened", "issues_created",
        "issues_refined", "reviews_completed", "blocked_items", "wait_reused",
        "wait_reuse_work", "handoff_ready", "next_queue", "quality_gate",
    }
    missing = sorted(required - record.keys())
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")
    if record["actor"] not in ACTORS:
        raise ValueError("invalid actor")
    if record["quality_gate"] not in QUALITY_GATES:
        raise ValueError("invalid quality_gate")
    for name in ("advanced_items", "prs_opened", "issues_created", "issues_refined", "reviews_completed", "blocked_items"):
        if not isinstance(record[name], int) or isinstance(record[name], bool) or record[name] < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    for name in ("advanced_item_refs", "wait_reuse_work", "handoff_ready", "next_queue"):
        value = record.get(name, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"{name} must be a list of non-empty strings")
    if "advanced_item_refs" in record and len(record["advanced_item_refs"]) > record["advanced_items"]:
        raise ValueError("advanced_item_refs cannot exceed advanced_items count")
    if not isinstance(record["wait_reused"], bool):
        raise ValueError("wait_reused must be boolean")
    reason = record.get("wait_not_reused_reason")
    if record["wait_reused"]:
        if not record["wait_reuse_work"]:
            raise ValueError("wait_reuse_work required when wait_reused=true")
        if reason is not None:
            raise ValueError("wait_not_reused_reason must be omitted when wait_reused=true")
    elif reason not in WAIT_REASONS:
        raise ValueError("wait_not_reused_reason required when wait_reused=false")
    if not isinstance(record["run_at"], str) or not record["run_at"]:
        raise ValueError("run_at required")
    return record


def identity(record: dict[str, Any]) -> str:
    raw = f'{record["actor"]}|{record["run_at"]}'
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def append_record(path: Path, record: dict[str, Any]) -> str:
    record = dict(validate_record(record))
    record["run_id"] = identity(record)
    rows = []
    if path.exists():
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for existing in rows:
        if existing.get("run_id") == record["run_id"]:
            if _canonical(existing) == _canonical(record):
                return "UNCHANGED"
            raise ValueError("run identity already exists with different payload")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical(record) + "\n")
    return "APPENDED"


def summarize(path: Path) -> dict[str, Any]:
    rows = [] if not path.exists() else [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {
        "runs": len(rows),
        "advanced_items": sum(row.get("advanced_items", 0) for row in rows),
        "prs_opened": sum(row.get("prs_opened", 0) for row in rows),
        "issues_created": sum(row.get("issues_created", 0) for row in rows),
        "issues_refined": sum(row.get("issues_refined", 0) for row in rows),
        "reviews_completed": sum(row.get("reviews_completed", 0) for row in rows),
        "blocked_items": sum(row.get("blocked_items", 0) for row in rows),
        "wait_reused_runs": sum(1 for row in rows if row.get("wait_reused")),
        "wait_eligible_runs": sum(1 for row in rows if row.get("wait_reused") or row.get("wait_not_reused_reason") != "NOT_APPLICABLE"),
        "quality_gate_counts": {gate: sum(1 for row in rows if row.get("quality_gate") == gate) for gate in sorted(QUALITY_GATES)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Append or summarize autonomous run throughput records")
    parser.add_argument("--ledger", default="data/operations/throughput-ledger.jsonl")
    parser.add_argument("--append")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    path = Path(args.ledger)
    if args.append:
        record = json.loads(Path(args.append).read_text(encoding="utf-8"))
        print(append_record(path, record))
    if args.summary:
        print(json.dumps(summarize(path), ensure_ascii=False, indent=2, sort_keys=True))
    if not args.append and not args.summary:
        parser.error("specify --append and/or --summary")


if __name__ == "__main__":
    main()
