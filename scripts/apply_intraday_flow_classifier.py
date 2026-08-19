"""Classify intraday subsector flow snapshots using threshold profiles.

Reads raw snapshots (flow_state=UNKNOWN), applies classification rules from
threshold profile, writes classified output.

Example:
    python scripts/apply_intraday_flow_classifier.py \\
        --input data/fixtures/intraday-subsector-flow-v1.json \\
        --profile data/config/intraday-flow-threshold-profile-v1.json \\
        --output data/generated/public/money-flow/classified.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.intraday_subsector_classifier_harness import (
    classify_acceleration,
    classify_flow,
    validate_threshold_profile,
)
from scripts.intraday_subsector_flow import validate_intraday_subsector_flow


def load_input_snapshots(path: Path) -> list[dict]:
    """Load from JSON array or JSONL format."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
        return [json.loads(ln) for ln in lines]
    payload = json.loads(text)
    return payload if isinstance(payload, list) else [payload]


def apply_classification(
    snapshots: list[dict], profile: dict
) -> list[dict]:
    """Apply flow and acceleration classification to each snapshot."""
    profile_validated = validate_threshold_profile(profile)
    results: list[dict] = []
    prev = None

    for raw in snapshots:
        snap = validate_intraday_subsector_flow(raw)
        flow_info = classify_flow(snap, profile_validated)
        
        classified = dict(snap)
        classified["flow_state"] = flow_info["flow_state"]
        
        if prev is not None:
            accel_info = classify_acceleration(prev, snap, profile_validated)
            classified["acceleration_state"] = accel_info["acceleration_state"]
        else:
            classified["acceleration_state"] = "UNKNOWN"
        
        results.append(classified)
        prev = snap
    
    return results


def write_output_jsonl(path: Path, snapshots: list[dict]) -> None:
    """Write snapshots as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(s) for s in snapshots]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_classifier() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Apply threshold profile classification to intraday flow snapshots"
    )
    parser.add_argument("--input", required=True, help="Input JSON or JSONL file")
    parser.add_argument("--profile", required=True, help="Threshold profile JSON")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    args = parser.parse_args()

    snapshots = load_input_snapshots(Path(args.input))
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    
    classified = apply_classification(snapshots, profile)
    write_output_jsonl(Path(args.output), classified)
    
    print(f"✓ Classified {len(classified)} snapshots → {args.output}")


if __name__ == "__main__":
    run_classifier()
