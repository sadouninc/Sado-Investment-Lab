import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from scripts.weekly_merge_metrics import (
    STATUS_UNKNOWN,
    STATUS_VERIFIED,
    main,
    parse_timestamp,
    summarize_weeks,
    week_start,
)

ROOT = Path(__file__).resolve().parents[1]
MONDAY = date(2099, 1, 5)  # synthetic Monday
FULL = {"complete": True, "since": "2099-01-01T00:00:00Z", "until": "2099-02-01T00:00:00Z"}


def pr(number, merged_at, merged=True):
    return {"number": number, "merged_at": merged_at, "merged": merged}


def run(records, weeks=2, coverage=FULL, first=MONDAY):
    return summarize_weeks(records, first_week=first, weeks=weeks, coverage=coverage)


def test_normal_weekly_counts_verified():
    r = run([
        pr(1, "2099-01-05T00:00:00+09:00"),  # Monday 00:00 JST, week 1
        pr(2, "2099-01-11T23:59:59+09:00"),  # Sunday end, week 1
        pr(3, "2099-01-12T00:00:00+09:00"),  # next Monday, week 2
    ])
    assert [(w["week_start_jst"], w["count"], w["prs"], w["status"]) for w in r["weeks"]] == [
        ("2099-01-05", 2, [1, 2], STATUS_VERIFIED),
        ("2099-01-12", 1, [3], STATUS_VERIFIED),
    ]
    assert r["total_in_window"] == 3
    assert r["all_weeks_verified"] is True


def test_utc_timestamp_crosses_into_jst_monday():
    # Sunday 15:00 UTC == Monday 00:00 JST
    r = run([pr(1, "2099-01-11T15:00:00Z"), pr(2, "2099-01-11T14:59:59Z")])
    assert r["weeks"][0]["prs"] == [2]
    assert r["weeks"][1]["prs"] == [1]


def test_week_start_helper():
    assert week_start(datetime(2099, 1, 11, 14, 59, 59, tzinfo=timezone.utc)) == date(2099, 1, 5)
    assert week_start(datetime(2099, 1, 11, 15, 0, 0, tzinfo=timezone.utc)) == date(2099, 1, 12)


def test_exact_duplicates_counted_once():
    rec = pr(1, "2099-01-06T10:00:00Z")
    r = run([rec, dict(rec), dict(rec)])
    assert r["weeks"][0]["count"] == 1
    assert r["deduplicated_records"] == 2
    assert r["all_weeks_verified"] is True


def test_conflicting_duplicate_is_unplaced_and_unknown():
    r = run([pr(1, "2099-01-06T10:00:00Z"), pr(1, "2099-01-13T10:00:00Z")])
    assert all(w["status"] == STATUS_UNKNOWN for w in r["weeks"])
    assert r["total_in_window"] == 0
    assert {"code": "CONFLICTING_DUPLICATE", "pr": 1} in r["anomalies"]


def test_unmerged_records_are_ignored_not_anomalies():
    r = run([pr(1, None, merged=False), {"number": 2, "merged_at": None}])
    assert r["total_in_window"] == 0
    assert r["anomalies"] == []
    assert r["all_weeks_verified"] is True


def test_merged_without_timestamp_makes_weeks_unknown():
    r = run([pr(1, "2099-01-06T10:00:00Z"), pr(2, None, merged=True)])
    assert r["weeks"][0]["count"] == 1  # observed lower bound kept
    assert all(w["status"] == STATUS_UNKNOWN for w in r["weeks"])
    assert any("could not be placed" in reason for reason in r["weeks"][0]["unknown_reasons"])


@pytest.mark.parametrize("bad", ["2099-01-06T10:00:00", "not-a-date", "", 12345, ["x"]])
def test_malformed_or_naive_merged_at(bad):
    r = run([pr(1, bad)])
    assert r["all_weeks_verified"] is False
    assert {"code": "MALFORMED_MERGED_AT", "pr": 1} in r["anomalies"]


def test_contradictory_merge_flag():
    r = run([pr(1, "2099-01-06T10:00:00Z", merged=False)])
    assert r["total_in_window"] == 0
    assert {"code": "CONTRADICTORY_MERGE_FLAG", "pr": 1} in r["anomalies"]


@pytest.mark.parametrize("bad", [None, "x", 1, {"number": "1"}, {"number": True}, {"number": 0}])
def test_malformed_records_do_not_raise(bad):
    r = run([bad])
    assert r["all_weeks_verified"] is False
    assert r["anomalies"][0]["code"] == "MALFORMED_RECORD"


def test_incomplete_or_missing_coverage_is_unknown():
    rec = [pr(1, "2099-01-06T10:00:00Z")]
    for cov in (None, {"complete": False, **{k: FULL[k] for k in ("since", "until")}}, {"complete": "yes"}):
        r = run(rec, coverage=cov)
        assert all(w["status"] == STATUS_UNKNOWN for w in r["weeks"]), cov
        assert r["weeks"][0]["count"] == 1


def test_partial_coverage_only_marks_uncovered_weeks():
    cov = {"complete": True, "since": "2099-01-04T15:00:00Z", "until": "2099-01-12T00:00:00+09:00"}
    r = run([pr(1, "2099-01-06T10:00:00Z")], coverage=cov)
    assert r["weeks"][0]["status"] == STATUS_VERIFIED
    assert r["weeks"][1]["status"] == STATUS_UNKNOWN
    assert "coverage does not reach week end" in r["weeks"][1]["unknown_reasons"]


def test_coverage_starting_after_week_start_is_unknown():
    cov = {"complete": True, "since": "2099-01-05T00:00:01+09:00", "until": "2099-02-01T00:00:00Z"}
    assert run([], coverage=cov)["weeks"][0]["status"] == STATUS_UNKNOWN


def test_malformed_coverage_timestamp():
    cov = {"complete": True, "since": "yesterday", "until": "2099-02-01T00:00:00Z"}
    r = run([], coverage=cov)
    assert {"code": "MALFORMED_COVERAGE"} in r["anomalies"]
    assert r["coverage"]["complete"] is False


def test_records_outside_window_reported_not_counted():
    r = run([pr(1, "2098-12-31T10:00:00Z"), pr(2, "2099-01-30T10:00:00Z")], weeks=1)
    assert r["total_in_window"] == 0
    assert r["outside_window_prs"] == [1, 2]


def test_zero_merge_week_is_verified_zero_not_unknown():
    r = run([], weeks=1)
    assert r["weeks"][0]["count"] == 0
    assert r["weeks"][0]["status"] == STATUS_VERIFIED


def test_invalid_window_arguments():
    with pytest.raises(ValueError):
        summarize_weeks([], first_week=date(2099, 1, 6), weeks=1)
    with pytest.raises(ValueError):
        summarize_weeks([], first_week=MONDAY, weeks=0)


def test_deterministic_regardless_of_input_order():
    recs = [pr(3, "2099-01-13T10:00:00Z"), pr(1, "2099-01-06T10:00:00Z"), pr(2, "2099-01-07T10:00:00Z")]
    a = run(recs)
    b = run(list(reversed(recs)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_parse_timestamp():
    assert parse_timestamp("2099-01-01T00:00:00Z") is not None
    assert parse_timestamp("2099-01-01T00:00:00") is None
    assert parse_timestamp(None) is None


def test_cli(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"records": [pr(1, "2099-01-06T10:00:00Z")], "coverage": FULL}), encoding="utf-8")
    out = tmp_path / "out.json"
    assert main(["--input", str(src), "--first-week", "2099-01-05", "--weeks", "2", "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["total_in_window"] == 1
    src.write_text(json.dumps({"records": [pr(1, "2099-01-06T10:00:00Z")]}), encoding="utf-8")
    assert main(["--input", str(src), "--first-week", "2099-01-05"]) == 1
    assert main(["--input", str(src), "--first-week", "2099-01-06"]) == 2
    src.write_text("[]", encoding="utf-8")
    assert main(["--input", str(src), "--first-week", "2099-01-05"]) == 2


def test_cli_module(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"records": [], "coverage": FULL}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.weekly_merge_metrics", "--input", str(src), "--first-week", "2099-01-05"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["weeks"][0]["status"] == STATUS_VERIFIED


# --- review 6099041948 regressions ------------------------------------------------


@pytest.mark.parametrize("flag", ["true", 1, 0, "false", [], {}])
def test_non_boolean_merge_flag_with_timestamp_is_malformed(flag):
    r = run([pr(1, "2099-01-06T10:00:00Z", merged=flag)])
    assert r["total_in_window"] == 0
    assert r["all_weeks_verified"] is False
    assert {"code": "MALFORMED_MERGE_FLAG", "pr": 1} in r["anomalies"]


@pytest.mark.parametrize("flag", ["true", 1, "no"])
def test_non_boolean_merge_flag_without_timestamp_is_not_verified_zero(flag):
    r = run([pr(1, None, merged=flag)])
    assert r["all_weeks_verified"] is False
    assert {"code": "MALFORMED_MERGE_FLAG", "pr": 1} in r["anomalies"]


def test_absent_or_null_flag_relies_on_timestamp():
    r = run([{"number": 1, "merged_at": "2099-01-06T10:00:00Z"}, {"number": 2, "merged_at": "2099-01-06T11:00:00Z", "merged": None}])
    assert r["weeks"][0]["prs"] == [1, 2]
    assert r["all_weeks_verified"] is True


@pytest.mark.parametrize(
    "other",
    [
        pr(1, None, merged=False),
        {"number": 1, "merged_at": None},
        pr(1, "2099-01-06T10:00:00Z", merged=False),
        pr(1, "garbage"),
        pr(1, "2099-01-06T10:00:00Z", merged="yes"),
        pr(1, None, merged=True),
    ],
)
def test_valid_record_plus_contradictory_record_excludes_pr_entirely(other):
    good = pr(1, "2099-01-06T10:00:00Z")
    for records in ([good, other], [other, good]):
        r = run(records + [pr(2, "2099-01-07T10:00:00Z")])
        assert r["weeks"][0]["prs"] == [2], other
        assert all(w["status"] == STATUS_UNKNOWN for w in r["weeks"])


@pytest.mark.parametrize(
    "value",
    ["0001-01-01T00:00:00+01:00", "0001-01-01T05:00:00+09:00", "9999-12-31T23:59:59-01:00", "9999-12-31T20:00:00Z"],
)
def test_extreme_timestamps_are_malformed_not_overflow(value):
    assert parse_timestamp(value) is None
    r = run([pr(1, value)])
    assert {"code": "MALFORMED_MERGED_AT", "pr": 1} in r["anomalies"]
    cov = {"complete": True, "since": value, "until": value}
    assert {"code": "MALFORMED_COVERAGE"} in run([], coverage=cov)["anomalies"]


def test_extreme_week_range_is_value_error():
    with pytest.raises(ValueError):
        summarize_weeks([], first_week=date(9999, 12, 27), weeks=2)
    with pytest.raises(ValueError):
        summarize_weeks([], first_week=date(1, 1, 1), weeks=1)


@pytest.mark.parametrize("cov", [["complete"], "complete", 1, True])
def test_non_mapping_coverage_is_malformed_not_crash(cov):
    r = run([pr(1, "2099-01-06T10:00:00Z")], coverage=cov)
    assert {"code": "MALFORMED_COVERAGE"} in r["anomalies"]
    assert r["coverage"]["complete"] is False
    assert all(w["status"] == STATUS_UNKNOWN for w in r["weeks"])


def test_cli_extreme_week_and_bad_coverage(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"records": [], "coverage": ["x"]}), encoding="utf-8")
    assert main(["--input", str(src), "--first-week", "2099-01-05"]) == 1
    src.write_text(json.dumps({"records": [], "coverage": FULL}), encoding="utf-8")
    assert main(["--input", str(src), "--first-week", "9999-12-27", "--weeks", "3"]) == 2
