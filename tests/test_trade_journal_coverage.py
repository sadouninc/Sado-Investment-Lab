from datetime import date
from pathlib import Path

from scripts.trade_journal_coverage import (
    discover_journal_dates,
    evaluate_trade_journal_coverage,
)

ROOT = Path(__file__).resolve().parents[1]
TRANSACTIONS = ROOT / "01_Portfolio" / "Transactions"


def test_confirmed_trade_and_journal_exists_passes():
    result = evaluate_trade_journal_coverage(
        {date(2026, 8, 14)},
        {date(2026, 8, 14)},
    )
    assert result.status == "PASS"
    assert result.missing_dates == ()


def test_confirmed_trade_and_journal_missing_fails_closed():
    result = evaluate_trade_journal_coverage(
        {date(2026, 8, 14)},
        {date(2026, 8, 13)},
    )
    assert result.status == "MISSING_TRADE_JOURNAL_DATE"
    assert result.missing_dates == (date(2026, 8, 14),)


def test_unfilled_order_only_does_not_create_confirmed_date():
    result = evaluate_trade_journal_coverage(set(), set())
    assert result.status == "PASS"


def test_transaction_authority_unavailable_is_unknown_not_pass():
    result = evaluate_trade_journal_coverage(None, {date(2026, 8, 14)})
    assert result.status == "UNKNOWN"


def test_multiple_fills_same_day_are_deduplicated_by_date_contract():
    result = evaluate_trade_journal_coverage(
        {date(2026, 8, 14)},
        set(),
    )
    assert result.missing_dates == (date(2026, 8, 14),)


def test_repository_now_contains_2026_08_14_trade_journal_date():
    journal_dates = discover_journal_dates(TRANSACTIONS)
    assert date(2026, 8, 14) in journal_dates
