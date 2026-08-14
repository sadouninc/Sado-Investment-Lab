#!/usr/bin/env python3
"""Build the #540 historical productivity baseline from explicit evidence fixtures."""

import importlib.util
import json
import math
from pathlib import Path

_COLLECTOR_PATH = Path(__file__).with_name("telemetry_collector.py")
_SPEC = importlib.util.spec_from_file_location("telemetry_collector", _COLLECTOR_PATH)
_COLLECTOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_COLLECTOR)

_ALLOWED_EXPLICIT_RESULTS = {"MERGED", "OPEN", "UNKNOWN"}


def safe_ratio(numerator, denominator):
    """Compute numerator / denominator for non-negative finite numeric inputs.

    Fail closed for missing, boolean, non-numeric, negative, non-finite, or
    zero-denominator inputs by returning ``None`` (UNKNOWN).
    """
    if numerator is None or denominator is None:
        return None
    if isinstance(numerator, bool) or isinstance(denominator, bool):
        return None
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
        return None
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    if numerator < 0 or denominator <= 0:
        return None
    return numerator / denominator


def build_case(case):
    record = _COLLECTOR.collect_from_fixture(case.get("event") or {})
    explicit_result = case.get("explicit_result")
    if explicit_result is not None:
        if explicit_result not in _ALLOWED_EXPLICIT_RESULTS:
            raise ValueError(f"unsupported explicit_result: {explicit_result}")
        record["result"] = explicit_result
    return {
        "case_id": case["case_id"],
        "case_class": case["case_class"],
        "evidence_quality": case["evidence_quality"],
        "source_refs": list(case.get("source_refs") or []),
        "telemetry": record,
    }


def build_dataset(payload):
    return [build_case(case) for case in payload.get("cases") or []]


def main(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as source:
        payload = json.load(source)
    records = build_dataset(payload)
    with open(output_path, "w", encoding="utf-8") as destination:
        for record in records:
            destination.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("usage: build_productivity_baseline.py INPUT_JSON OUTPUT_JSONL")
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2])
