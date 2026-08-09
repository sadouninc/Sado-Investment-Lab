import json
import sqlite3

import pytest

from scripts.decision_execution_sbi_adapter import (
    DecisionExecutionAdapterError,
    build_actual_execution_from_sbi_db,
    build_actual_execution_from_sbi_rows,
    sbi_execution_ref,
)


def row(
    fingerprint="fp1",
    *,
    code="6622",
    side="BUY",
    transaction="信用新規買",
    product="国内株式 信用",
    quantity=100,
    price=12340,
    time_value="10:15:00",
):
    raw = {"約定時刻": time_value} if time_value is not None else {}
    return {
        "fingerprint": fingerprint,
        "trade_date": "2026-08-09",
        "product": product,
        "transaction_type": transaction,
        "side": side,
        "security_code": code,
        "quantity": quantity,
        "price": price,
        "raw_json": json.dumps(raw, ensure_ascii=False),
    }


def portfolio(snapshot_id, positions, status="VERIFIED", as_of="2026-08-09"):
    return {
        "as_of": as_of,
        "verification_status": status,
        "authority": "sbi_verified_position_snapshot",
        "base_snapshot": snapshot_id,
        "source_references": {"snapshot_id": snapshot_id},
        "positions": positions,
    }


def pos(code="6622", position_type="margin_long", quantity=100):
    return {
        "security_code": code,
        "position_type": position_type,
        "quantity": quantity,
    }


def build_with(row_value, before, after, execution_status="EXECUTED"):
    ref = sbi_execution_ref(row_value)
    return build_actual_execution_from_sbi_rows(
        decision_ref="decision:6622:1",
        security_code="6622",
        captured_at="2026-08-09T16:00:00+09:00",
        rows=[row_value],
        execution_refs=[ref],
        execution_status=execution_status,
        source_timezone="+09:00",
        portfolio_before=before,
        portfolio_after=after,
    )


def test_confirmed_sbi_buy_builds_actual_fill_and_buy_action():
    actual = build_with(
        row("buy1"),
        portfolio("before", []),
        portfolio("after", [pos(quantity=100)]),
    )
    assert actual["execution_status"] == "EXECUTED"
    assert actual["actual_action"] == "BUY"
    assert actual["fills"][0]["quantity"] == 100
    assert actual["fills"][0]["executed_at"] == "2026-08-09T10:15:00+09:00"
    assert actual["fills"][0]["source_ref"] == "sbi-execution:buy1"
    assert actual["portfolio_verification"]["status"] == "CONSISTENT"


def test_verified_position_change_distinguishes_add_reduce_and_sell():
    add = build_with(
        row("add1"),
        portfolio("b1", [pos(quantity=100)]),
        portfolio("a1", [pos(quantity=200)]),
    )
    reduce = build_with(
        row("reduce1", side="SELL", transaction="信用返済売"),
        portfolio("b2", [pos(quantity=200)]),
        portfolio("a2", [pos(quantity=100)]),
    )
    sell = build_with(
        row("sell1", side="SELL", transaction="信用返済売"),
        portfolio("b3", [pos(quantity=100)]),
        portfolio("a3", []),
    )
    assert add["actual_action"] == "ADD"
    assert reduce["actual_action"] == "REDUCE"
    assert sell["actual_action"] == "SELL"


def test_short_open_and_cover_use_authoritative_position_direction():
    short_open = build_with(
        row("short1", side="SELL", transaction="信用新規売"),
        portfolio("b1", []),
        portfolio("a1", [pos(position_type="margin_short", quantity=100)]),
    )
    cover = build_with(
        row("cover1", side="BUY", transaction="信用返済買"),
        portfolio("b2", [pos(position_type="margin_short", quantity=100)]),
        portfolio("a2", []),
    )
    assert short_open["actual_action"] == "SHORT_OPEN"
    assert cover["actual_action"] == "COVER"


def test_date_only_sbi_source_does_not_invent_execution_time():
    value = row("dateonly", time_value=None)
    actual = build_with(
        value,
        portfolio("before", []),
        portfolio("after", [pos(quantity=100)]),
    )
    assert actual["execution_status"] == "UNKNOWN"
    assert actual["actual_action"] == "UNKNOWN"
    assert actual["fills"] == []
    assert "SBI_EXECUTION_TIME_DATE_ONLY_SOURCE" in actual["adapter_diagnostics"]


def test_missing_timezone_does_not_assume_jst():
    value = row("tzmissing")
    ref = sbi_execution_ref(value)
    actual = build_actual_execution_from_sbi_rows(
        decision_ref="decision:1",
        security_code="6622",
        captured_at="2026-08-09T16:00:00+09:00",
        rows=[value],
        execution_refs=[ref],
        execution_status="EXECUTED",
        source_timezone=None,
    )
    assert actual["execution_status"] == "UNKNOWN"
    assert "SBI_EXECUTION_TIME_TIMEZONE_MISSING" in actual["adapter_diagnostics"]


def test_non_verified_portfolio_never_invents_buy_vs_add():
    value = row("p1")
    actual = build_with(
        value,
        portfolio("before", [pos(quantity=100)], status="PROVISIONAL"),
        portfolio("after", [pos(quantity=200)]),
    )
    assert actual["fills"]
    assert actual["actual_action"] == "UNKNOWN"
    assert actual["portfolio_verification"]["status"] == "UNKNOWN"


def test_position_mismatch_is_diagnostic_not_rewritten_execution():
    value = row("mismatch")
    actual = build_with(
        value,
        portfolio("before", [pos(quantity=100)]),
        portfolio("after", [pos(quantity=50)]),
    )
    assert actual["fills"][0]["side"] == "BUY"
    assert actual["actual_action"] == "UNKNOWN"
    assert actual["portfolio_verification"]["status"] == "MISMATCH"


def test_not_executed_requires_explicit_empty_authoritative_scope():
    actual = build_actual_execution_from_sbi_rows(
        decision_ref="decision:none",
        security_code="6622",
        captured_at="2026-08-09T16:00:00+09:00",
        rows=[],
        execution_refs=[],
        execution_status="NOT_EXECUTED",
        source_status="CURRENT",
    )
    assert actual["execution_status"] == "NOT_EXECUTED"
    assert actual["fills"] == []


def test_row_ref_must_match_fingerprint():
    with pytest.raises(DecisionExecutionAdapterError):
        build_actual_execution_from_sbi_rows(
            decision_ref="decision:bad",
            security_code="6622",
            captured_at="2026-08-09T16:00:00+09:00",
            rows=[row("actual")],
            execution_refs=["sbi-execution:different"],
            execution_status="EXECUTED",
            source_timezone="+09:00",
        )


def test_database_missing_is_unknown_not_not_executed(tmp_path):
    actual = build_actual_execution_from_sbi_db(
        database=tmp_path / "missing.sqlite",
        decision_ref="decision:missing",
        security_code="6622",
        captured_at="2026-08-09T16:00:00+09:00",
        execution_refs=["sbi-execution:fp1"],
        execution_status="EXECUTED",
        source_timezone="+09:00",
    )
    assert actual["source_status"] == "UNAVAILABLE"
    assert actual["execution_status"] == "UNKNOWN"
    assert actual["fills"] == []
    assert "SBI_SOURCE_UNAVAILABLE" in actual["adapter_diagnostics"]


def _create_execution_table(db):
    db.execute(
        """CREATE TABLE executions (
            fingerprint TEXT PRIMARY KEY,
            trade_date TEXT,
            product TEXT,
            transaction_type TEXT,
            side TEXT,
            security_code TEXT,
            quantity REAL,
            price REAL,
            raw_json TEXT
        )"""
    )


def _insert_execution(db, value):
    db.execute(
        "INSERT INTO executions VALUES (?,?,?,?,?,?,?,?,?)",
        tuple(
            value[key]
            for key in (
                "fingerprint",
                "trade_date",
                "product",
                "transaction_type",
                "side",
                "security_code",
                "quantity",
                "price",
                "raw_json",
            )
        ),
    )


def test_missing_explicit_execution_ref_is_unknown(tmp_path):
    db_path = tmp_path / "trades.sqlite"
    with sqlite3.connect(db_path) as db:
        _create_execution_table(db)
        _insert_execution(db, row("known"))

    actual = build_actual_execution_from_sbi_db(
        database=db_path,
        decision_ref="decision:missing-ref",
        security_code="6622",
        captured_at="2026-08-09T16:00:00+09:00",
        execution_refs=["sbi-execution:not-there"],
        execution_status="EXECUTED",
        source_timezone="+09:00",
    )
    assert actual["execution_status"] == "UNKNOWN"
    assert actual["fills"] == []
    assert "SBI_EXECUTION_REF_MISSING" in actual["adapter_diagnostics"]


def test_database_adapter_preserves_explicit_sbi_ref(tmp_path):
    db_path = tmp_path / "trades.sqlite"
    value = row("db1")
    with sqlite3.connect(db_path) as db:
        _create_execution_table(db)
        _insert_execution(db, value)

    actual = build_actual_execution_from_sbi_db(
        database=db_path,
        decision_ref="decision:db",
        security_code="6622",
        captured_at="2026-08-09T16:00:00+09:00",
        execution_refs=["sbi-execution:db1"],
        execution_status="EXECUTED",
        source_timezone="+09:00",
        portfolio_before=portfolio("before", []),
        portfolio_after=portfolio("after", [pos(quantity=100)]),
    )
    assert actual["fills"][0]["source_ref"] == "sbi-execution:db1"
    assert actual["actual_action"] == "BUY"


def test_inputs_are_not_mutated():
    value = row("immutable")
    before = portfolio("before", [])
    after = portfolio("after", [pos(quantity=100)])
    original_row = json.loads(json.dumps(value))
    original_before = json.loads(json.dumps(before))
    original_after = json.loads(json.dumps(after))
    build_with(value, before, after)
    assert value == original_row
    assert before == original_before
    assert after == original_after
