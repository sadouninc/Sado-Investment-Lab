from __future__ import annotations

"""Read-only CLI: Queue Selection Packet.

This CLI feeds validated GitHub Issue payloads into the existing Queue
Auto-Promotion selector (``scripts.queue_auto_promotion.select_next_work``)
via the existing Work Contract adapter
(``scripts.queue_candidate_adapter.build_queue_candidate``) and prints one
deterministic JSON "selection packet" to stdout.

It performs no GitHub writes (no assignment, comment, merge, etc.) and does
not reimplement the pure selector or the Work Contract adapter/preflight —
it only wires their existing, tested behaviour to local JSON files so the
same logic can be exercised locally or from GitHub Actions as a read-only
step.

Inputs (all local JSON files, no network access):

* ``--issues``      JSON file containing a list of GitHub Issue payload
                     objects (``number``, ``state``, ``title``, ``body``,
                     optionally ``pull_request``).
* ``--worker-state`` JSON file mapping worker name -> state string (for
                     example ``{"copilot": "available", "kai":
                     "quota_blocked"}``).
* ``--assignments``  JSON file mapping issue number (string or int) to an
                     object with ``preferred_worker`` (str),
                     ``dependencies_satisfied`` (bool, explicit dependency
                     truth), and optional ``priority`` (int, default 999).
                     An issue with no entry is treated fail-closed as
                     unassigned with ``dependencies_satisfied=False``.
* ``--active-owner-slices`` optional JSON file with a list of owner_slice
                     strings already in flight.
* ``--active-paths`` optional JSON file with a list of paths already in
                     flight.
* ``--output``       optional path to also write the packet JSON to.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.queue_auto_promotion import select_next_work
from scripts.queue_candidate_adapter import build_queue_candidate

DEFAULT_PRIORITY = 999


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_list(path: Path | None) -> list[str]:
    if path is None:
        return []
    payload = load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path}: expected a JSON list")
    return [str(item) for item in payload]


def _issue_number(issue: Mapping[str, Any]) -> int:
    return int(issue.get("number", 0))


def build_candidates(
    issues: Iterable[Mapping[str, Any]],
    assignments: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build one queue candidate per Issue via the existing adapter.

    Issues are processed in a deterministic order (sorted by issue number)
    regardless of input ordering, so the resulting packet is stable for the
    same input set.
    """
    candidates: list[dict[str, Any]] = []
    for issue in sorted(issues, key=_issue_number):
        number = _issue_number(issue)
        assignment = assignments.get(str(number)) or {}
        candidates.append(
            build_queue_candidate(
                issue,
                preferred_worker=str(assignment.get("preferred_worker") or "unassigned"),
                dependencies_satisfied=bool(assignment.get("dependencies_satisfied", False)),
                priority=int(assignment.get("priority", DEFAULT_PRIORITY)),
            )
        )
    return candidates


def build_selection_packet(
    issues: Iterable[Mapping[str, Any]],
    *,
    assignments: Mapping[str, Any],
    worker_states: Mapping[str, str],
    active_owner_slices: Iterable[str] = (),
    active_paths: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a deterministic read-only selection packet.

    Delegates entirely to the existing pure selector and Work Contract
    adapter; performs no GitHub writes.
    """
    candidates = build_candidates(issues, assignments)
    result = select_next_work(
        candidates,
        worker_states=worker_states,
        active_owner_slices=active_owner_slices,
        active_paths=active_paths,
    )
    return {
        "schema_version": 1,
        "status": result["status"],
        "selected": result["selected"],
        "metrics": result["metrics"],
        "candidates": candidates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Queue Selection Packet CLI (no GitHub writes)"
    )
    parser.add_argument("--issues", required=True, type=Path, help="JSON list of Issue payloads")
    parser.add_argument("--worker-state", required=True, type=Path, help="JSON worker state map")
    parser.add_argument(
        "--assignments",
        type=Path,
        default=None,
        help="JSON map of issue number -> {preferred_worker, dependencies_satisfied, priority}",
    )
    parser.add_argument("--active-owner-slices", type=Path, default=None)
    parser.add_argument("--active-paths", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        issues = load_json(args.issues)
        if not isinstance(issues, list):
            raise ValueError(f"{args.issues}: expected a JSON list of Issue payloads")
        worker_states = load_json(args.worker_state)
        if not isinstance(worker_states, dict):
            raise ValueError(f"{args.worker_state}: expected a JSON object")
        assignments = load_json(args.assignments) if args.assignments else {}
        if not isinstance(assignments, dict):
            raise ValueError(f"{args.assignments}: expected a JSON object")
        active_owner_slices = load_optional_list(args.active_owner_slices)
        active_paths = load_optional_list(args.active_paths)
        packet = build_selection_packet(
            issues,
            assignments=assignments,
            worker_states=worker_states,
            active_owner_slices=active_owner_slices,
            active_paths=active_paths,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"queue selection packet error: {exc}\n")

    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if packet["status"] == "SELECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
